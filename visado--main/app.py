# app.py

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta
import json
import uuid
from collections import deque

app = Flask(__name__)
# CRÍTICO: Asegúrate de tener una secret_key para usar 'session' de Flask
app.secret_key = 'visa_scheduling_secret_key_2024'

################################################################################
### CHATBOT: CONSTANTES DE ESTADO
################################################################################
STATE_MAIN_MENU = 'main_menu'
STATE_BOOKING_ASK_ID = 'booking_ask_id'
STATE_BOOKING_ASK_VISA = 'booking_ask_visa'
STATE_BOOKING_ASK_DATE = 'booking_ask_date'
STATE_BOOKING_ASK_TIME = 'booking_ask_time'
STATE_CONSULT_ASK_DATE = 'consult_ask_date'
STATE_CONSULT_POST_AVAILABILITY = 'consult_post_availability'
STATE_MANAGE_ASK_CODE = 'manage_ask_code'
STATE_MANAGE_SUB_MENU = 'manage_sub_menu'

################################################################################
### LÓGICA DEL SISTEMA DE AGENDAMIENTO
################################################################################
class VisaSchedulingSystem:
    def __init__(self):
        self.slots = {}
        self.waiting_queue = deque()
        self.modules = {1: None, 2: None, 3: None, 4: None, 5: None} # 5 módulos de atención (Estado: None=Libre, ID=Ocupado)
        self.appointments = {}
        self.initialize_slots()
    
    def initialize_slots(self):
        # Inicializar slots para los próximos 30 días
        start_date = datetime.now().date()
        for i in range(30):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            # Horarios de 9:00 a 11:00 y 14:00 a 16:00, con máx 10 por hora
            self.slots[date_str] = {
                '09:00': {'count': 0, 'max': 10, 'available': 10},
                '10:00': {'count': 0, 'max': 10, 'available': 10},
                '11:00': {'count': 0, 'max': 10, 'available': 10},
                '14:00': {'count': 0, 'max': 10, 'available': 10},
                '15:00': {'count': 0, 'max': 10, 'available': 10},
                '16:00': {'count': 0, 'max': 10, 'available': 10},
            }

    # MÉTODO AUXILIAR DE TU CÓDIGO ORIGINAL (Adaptado para el chatbot)
    def get_available_slots(self, date_str):
        """Obtiene los slots disponibles para una fecha específica."""
        return self.slots.get(date_str, {})
        
    # MÉTODO CENTRAL PARA LA RESERVA (Usado por el chatbot y /resultado)
    def book_appointment(self, user_id, date_str, time_str, visa_type):
        """Agenda una cita, y devuelve su ID de confirmación."""
        if date_str in self.slots and time_str in self.slots[date_str]:
            slot = self.slots[date_str][time_str]
            if slot['available'] > 0:
                slot['count'] += 1
                slot['available'] -= 1
                
                appointment_id = str(uuid.uuid4())
                self.appointments[appointment_id] = {
                    'id': appointment_id,
                    'user_id': user_id,
                    'date_str': date_str,
                    'time_str': time_str,
                    'visa_type': visa_type,
                    'created_at': datetime.now().isoformat()
                }
                return appointment_id
        return None

    # MÉTODO CRÍTICO: CANCELACIÓN Y LIBERACIÓN DE CUPO
    def cancel_appointment(self, appointment_id):
        """Cancela una cita por ID, elimina de appointments y libera el slot."""
        
        appointment = self.appointments.pop(appointment_id, None)
        
        if appointment:
            # Manejo de claves por si usaste 'date'/'time' en lugar de 'date_str'/'time_str'
            date_str = appointment.get('date_str') or appointment.get('date')
            time_str = appointment.get('time_str') or appointment.get('time')
            
            # CRÍTICO: Liberar el slot
            if date_str in self.slots and time_str in self.slots[date_str]:
                self.slots[date_str][time_str]['count'] -= 1
                self.slots[date_str][time_str]['available'] += 1
            
            return True
        return False
        
    # MÉTODO CRÍTICO: MODIFICACIÓN DE CITA
    def update_appointment(self, appointment_id, new_date_str, new_time_str):
        """Maneja la modificación de citas, liberando el slot antiguo y reservando el nuevo."""
        old_appointment = self.appointments.get(appointment_id)
        
        if not old_appointment:
            return False

        old_date_str = old_appointment.get('date_str') or old_appointment.get('date')
        old_time_str = old_appointment.get('time_str') or old_appointment.get('time')
        
        # 1. Intentar reservar el nuevo slot
        if new_date_str in self.slots and new_time_str in self.slots[new_date_str]:
            new_slot = self.slots[new_date_str][new_time_str]
            if new_slot['available'] > 0:
                
                # 2. Liberar el slot antiguo
                if old_date_str in self.slots and old_time_str in self.slots[old_date_str]:
                    self.slots[old_date_str][old_time_str]['count'] -= 1
                    self.slots[old_date_str][old_time_str]['available'] += 1

                # 3. Reservar el nuevo slot
                new_slot['count'] += 1
                new_slot['available'] -= 1
                
                # 4. Actualizar la cita en el registro
                self.appointments[appointment_id]['date_str'] = new_date_str
                self.appointments[appointment_id]['time_str'] = new_time_str
                return True
        
        return False

    # MÉTODO CORREGIDO: Solución al error 'modules_status' is undefined
    def get_admin_stats(self):
        """Calcula y devuelve las estadísticas necesarias para el panel de administración."""
        
        total_citas = len(self.appointments)
        available_slots_count = 0
        total_slots = 0
        
        # Recorrer todos los slots para contar disponibilidad
        for date, slots_by_time in self.slots.items():
            for time, data in slots_by_time.items():
                available_slots_count += data['available']
                total_slots += data['max']
                
        # Calcular citas por tipo de visa
        visa_counts = {}
        for appointment in self.appointments.values():
            visa = appointment.get('visa_type', 'N/A')
            visa_counts[visa] = visa_counts.get(visa, 0) + 1

        return {
            'total_citas': total_citas,
            'cupos_disponibles': available_slots_count,
            'total_cupos': total_slots,
            'citas_por_visa': visa_counts,
            'appointments_list': list(self.appointments.values()),
            'modules_status': self.modules  # <--- CORRECCIÓN IMPLEMENTADA
        }


# Inicializar el sistema al inicio de la aplicación
scheduling_system = VisaSchedulingSystem()


################################################################################
### CHATBOT: FUNCIONES Y RUTAS DEL CHAT
################################################################################

def get_main_menu_text():
    """Función de ayuda para enviar el menú principal."""
    return (
        "¡Hola! Soy tu asistente virtual para el agendamiento de citas de visa. "
        "Por favor, selecciona la opción que deseas realizar:\n\n"
        "**1**. Agendar una nueva cita.\n"
        "**2**. Consultar disponibilidad de horarios.\n"
        "**3**. Modificar o Cancelar una cita existente.\n"
        "**4**. Finalizar la conversación."
    )

# La función index, agendar, resultado y admin quedan IGUALES a como las tenías
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/agendar')
def agendar():
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('agendar.html', today=today)

# Ruta /resultado corregida para usar book_appointment
@app.route('/resultado', methods=['POST'])
def resultado():
    # Asume que los datos del formulario contienen la fecha, hora y pasaporte (ID de usuario)
    preferred_date = request.form['date']
    preferred_time = request.form['time']
    visa_type = request.form.get('visa_type', 'Desconocida') # Asegúrate de que este campo exista en tu HTML
    user_id = request.form['passport'] # Asume que el campo se llama 'passport'
    
    appointment_id = scheduling_system.book_appointment(
        user_id, preferred_date, preferred_time, visa_type
    )
    
    if appointment_id:
        result = {
            'status': 'success',
            'message': 'Cita agendada con éxito.',
            'confirmation_code': appointment_id,
            'date': preferred_date,
            'time': preferred_time
        }
    else:
         result = {
            'status': 'error',
            'message': 'No se pudo agendar la cita. El cupo ya no está disponible.',
            'date': preferred_date,
            'time': preferred_time
        }
    
    return render_template('resultado.html', result=result)

@app.route('/admin')
def admin():
    # Llama al método corregido
    stats_data = scheduling_system.get_admin_stats()
    
    # Se pasan los datos a la plantilla
    return render_template(
        'admin.html', 
        stats=stats_data, 
        appointments=stats_data['appointments_list']
    )


@app.route('/chatbot_api', methods=['POST'])
def chatbot_api():
    """Ruta principal que maneja el flujo conversacional del chatbot."""
    user_input = request.json.get('message', '').strip()
    
    # Manejar navegación rápida: si el usuario escribe 'MENU', vuelve al inicio
    if user_input.upper() == 'MENU':
        session['state'] = STATE_MAIN_MENU
        return jsonify({'response': get_main_menu_text()})

    # Inicializar estado si no está presente
    current_state = session.get('state', STATE_MAIN_MENU)
    
    # --- LÓGICA DEL MENÚ PRINCIPAL ---
    if current_state == STATE_MAIN_MENU:
        if user_input == '1':
            session['state'] = STATE_BOOKING_ASK_ID
            session['booking_data'] = {} 
            session.pop('manage_id', None) 
            return jsonify({'response': 'Para agendar, por favor ingresa tu **número de identificación** (o pasaporte).'})
        elif user_input == '2':
            session['state'] = STATE_CONSULT_ASK_DATE
            return jsonify({'response': 'Para consultar disponibilidad, ingresa la **fecha** deseada (YYYY-MM-DD).'})
        elif user_input == '3':
            session['state'] = STATE_MANAGE_ASK_CODE
            return jsonify({'response': 'Para modificar o cancelar, ingresa el **código de confirmación** de tu cita.'})
        elif user_input == '4':
            session.clear()
            return jsonify({'response': '¡Gracias por usar nuestro servicio! La conversación ha finalizado.'})
        else:
            return jsonify({'response': get_main_menu_text()})
            
    # --- FLUJO DE AGENDAMIENTO (Opción 1) ---
    elif current_state == STATE_BOOKING_ASK_ID:
        session['booking_data']['user_id'] = user_input
        session['state'] = STATE_BOOKING_ASK_VISA
        return jsonify({'response': 'Gracias. ¿Qué tipo de visa deseas solicitar? (Ej: **A**. Turista, **B**. Estudio, **C**. Trabajo)'})

    elif current_state == STATE_BOOKING_ASK_VISA:
        session['booking_data']['visa_type'] = user_input
        session['state'] = STATE_BOOKING_ASK_DATE
        return jsonify({'response': 'Por favor, ingresa la **fecha** en la que deseas agendar (YYYY-MM-DD).'})

    elif current_state == STATE_BOOKING_ASK_DATE:
        # Lógica para validar fecha y mostrar slots
        date_str = user_input
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            slots = scheduling_system.get_available_slots(date_str)
            
            available_times = {h: data for h, data in slots.items() if data['available'] > 0}
            
            if not available_times:
                 return jsonify({'response': f'No hay disponibilidad para el {date_str}. Ingresa **otra fecha** (YYYY-MM-DD) o escribe **MENU**.'})

            session['booking_data']['date_str'] = date_str
            session['available_slots'] = slots 
            session['state'] = STATE_BOOKING_ASK_TIME
            
            times = ", ".join(available_times.keys())
            
            return jsonify({'response': f'Para el {date_str} tenemos disponibilidad a las siguientes horas: **{times}**. Por favor, selecciona la **hora** que prefieras (HH:MM).'})

        except ValueError:
            return jsonify({'response': 'Formato de fecha incorrecto. Ingresa la fecha en formato **YYYY-MM-DD**.'})

    elif current_state == STATE_BOOKING_ASK_TIME:
        # Lógica para finalizar Agendamiento O Modificación
        time_str = user_input
        date_str = session['booking_data']['date_str']
        slots = session.get('available_slots', {})
        
        if time_str in slots and slots[time_str]['available'] > 0:
            
            appointment_id_to_manage = session.get('manage_id')
            
            if appointment_id_to_manage:
                # MODIFICACIÓN DE CITA
                if scheduling_system.update_appointment(appointment_id_to_manage, date_str, time_str):
                    session.clear()
                    return jsonify({'response': f'✅ Cita **modificada** con éxito a las **{time_str}** del **{date_str}**. Tu código sigue siendo **{appointment_id_to_manage}**. Escribe **MENU** para volver al inicio.'})
                else:
                    session['state'] = STATE_MAIN_MENU
                    return jsonify({'response': f'Hubo un error al modificar la cita. El slot ya fue ocupado o la nueva fecha es inválida. Escribe **MENU**.'})
            else:
                # NUEVO AGENDAMIENTO
                user_id = session['booking_data']['user_id']
                visa_type = session['booking_data']['visa_type']
                
                appointment_id = scheduling_system.book_appointment(user_id, date_str, time_str, visa_type)
                
                if appointment_id:
                    session.clear()
                    return jsonify({'response': f'✅ ¡Cita agendada con éxito! Tu **código de confirmación** es **{appointment_id}**. Escribe **MENU** para volver al inicio.'})
                else:
                    session['state'] = STATE_MAIN_MENU
                    return jsonify({'response': 'El cupo se agotó justo ahora. Vuelve a intentar agendar (escribe **MENU**).'})

        else:
            times = ", ".join([h for h, data in slots.items() if data['available'] > 0])
            return jsonify({'response': f'Hora no válida o ya ocupada. Selecciona una hora disponible: **{times}**.'})
            
    # --- FLUJO DE CONSULTA (Opción 2) ---
    elif current_state == STATE_CONSULT_ASK_DATE:
        date_str = user_input
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            slots = scheduling_system.get_available_slots(date_str)

            availability_list = [f"**{h}**: {data['available']} cupos" for h, data in slots.items() if data['available'] > 0]
            
            if availability_list:
                availability_text = "\n".join(availability_list)
                response = f"La disponibilidad para el **{date_str}** es:\n{availability_text}\n\n¿Deseas agendar una cita ahora? (Sí/No) o escribe **MENU** para volver."
                session['state'] = STATE_CONSULT_POST_AVAILABILITY
            else:
                response = f'Lo sentimos, no quedan cupos disponibles para el {date_str}. Escribe **MENU** para volver.'
            
            return jsonify({'response': response})

        except ValueError:
            return jsonify({'response': 'Formato de fecha incorrecto. Ingresa la fecha en formato **YYYY-MM-DD**.'})

    elif current_state == STATE_CONSULT_POST_AVAILABILITY:
        if user_input.lower() in ['si', 'sí']:
            session['state'] = STATE_BOOKING_ASK_ID
            return jsonify({'response': '¡Perfecto! Vamos a agendar. Por favor ingresa tu **número de identificación**.'})
        else:
            session['state'] = STATE_MAIN_MENU
            return jsonify({'response': get_main_menu_text()})
            
    # --- FLUJO DE GESTIÓN (Modificar/Cancelar - Opción 3) ---
    elif current_state == STATE_MANAGE_ASK_CODE:
        appointment_id = user_input
        appointment = scheduling_system.appointments.get(appointment_id)
        
        if appointment:
            # Adaptación para mostrar la información correcta
            date_info = appointment.get('date_str') or appointment.get('date', 'N/A')
            time_info = appointment.get('time_str') or appointment.get('time', 'N/A')
            visa_info = appointment.get('visa_type') or 'N/A'
            
            session['manage_id'] = appointment_id # Guardar ID de la cita a gestionar
            session['state'] = STATE_MANAGE_SUB_MENU
            return jsonify({'response': f'Cita encontrada para el **{date_info}** a las **{time_info}** (Visa {visa_info}). ¿Qué deseas hacer?\n**3.1**. Modificar fecha u hora.\n**3.2**. Cancelar la cita.'})
        else:
            return jsonify({'response': 'Código de confirmación no encontrado. Por favor, verifica el código o escribe **MENU** para volver.'})

    elif current_state == STATE_MANAGE_SUB_MENU:
        appointment_id = session.get('manage_id')
        
        if user_input == '3.2':
            # CANCELAR (Usa el método corregido con liberación de cupo)
            if scheduling_system.cancel_appointment(appointment_id):
                 session.clear()
                 return jsonify({'response': '❌ Tu cita ha sido **cancelada** con éxito y el cupo ha sido liberado. Escribe **MENU**.'})
            else:
                 session.clear()
                 return jsonify({'response': 'Hubo un error al cancelar. Escribe **MENU** para volver al inicio.'})

        elif user_input == '3.1':
            # MODIFICAR (Reutilizamos el flujo de agendamiento)
            session['booking_data'] = {} # Limpiar datos de reserva, solo se mantiene el 'manage_id'
            session['state'] = STATE_BOOKING_ASK_DATE
            return jsonify({'response': 'Ingresa la **nueva fecha** para tu cita (YYYY-MM-DD).'})
        
        else:
            return jsonify({'response': 'Opción no válida. Selecciona **3.1** para Modificar o **3.2** para Cancelar.'})

    # --- RESPUESTA POR DEFECTO ---
    return jsonify({'response': f'Opción no reconocida en el estado actual. Escribe **MENU** para volver al menú principal.'})


if __name__ == '__main__':
    app.run(debug=True)