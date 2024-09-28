import telebot
import json
import datetime
import threading
import time

# Reemplaza 'TU_TOKEN_DE_BOT' con tu token real
bot = telebot.TeleBot('7616020867:AAE8Ie_BeafE00C34-IHgTyE9wdjagtsQaA')
chat_id = -1002269439255  # Cambia por tu chat ID si es necesario


# Cargar datos de usuarios desde archivos JSON
def cargar_datos():
    global usuarios
    try:
        with open('usuarios.json', 'r') as f:
            usuarios = json.load(f)
    except FileNotFoundError:
        usuarios = {}

# Guardar datos de usuarios en archivos JSON
def guardar_datos():
    with open('usuarios.json', 'w') as f:
        json.dump(usuarios, f, indent=4)

def agregar_o_actualizar_usuario(usuario_id, nombre):
    usuario_id_str = str(usuario_id)
    if usuario_id_str not in usuarios:
        usuarios[usuario_id_str] = {
            'nombre': nombre,
            'numeroMensajes': 0,
            'ultimaActividad': str(datetime.datetime.now()),
            'AFK': False,
            'motivoAFK': None
        }
    else:
        # Si el usuario está AFK y manda un mensaje, sale del estado AFK
        if usuarios[usuario_id_str]['AFK']:
            ultima_actividad = datetime.datetime.strptime(usuarios[usuario_id_str]['ultimaActividad'],
                                                          '%Y-%m-%d %H:%M:%S.%f')
            tiempo_afk = datetime.datetime.now() - ultima_actividad
            minutos_afk = tiempo_afk.seconds // 60

            # Salir del estado AFK
            usuarios[usuario_id_str]['AFK'] = False
            usuarios[usuario_id_str]['motivoAFK'] = None

            # Notificar que el usuario ha vuelto
            bot.send_message(chat_id, f"{nombre} ha vuelto de estar AFK después de {minutos_afk} minutos.")

        usuarios[usuario_id_str]['numeroMensajes'] += 1
        usuarios[usuario_id_str]['ultimaActividad'] = str(datetime.datetime.now())

    guardar_datos()


def es_admin(usuario_id):
    administradores = bot.get_chat_administrators(chat_id)
    return any(admin.user.id == usuario_id for admin in administradores)

# Verificar si el usuario es un bot
def es_bot(usuario_id):
    user = bot.get_chat_member(chat_id, usuario_id).user
    return user.is_bot

# Comando /inactivos solo disponible en privado para administradores
@bot.message_handler(commands=['inactivos'])
def handle_inactivos(message):
    if message.chat.type != 'private':
        bot.reply_to(message, "Este comando solo puede ser usado en privado.")
        return

    if es_admin(message.from_user.id):
        # Ordenar por tiempo de inactividad (diferencia entre la fecha actual y la última actividad)
        usuarios_ordenados = sorted(
            usuarios.items(),
            key=lambda x: datetime.datetime.now() - datetime.datetime.strptime(x[1]['ultimaActividad'],
                                                                               '%Y-%m-%d %H:%M:%S.%f'),
            reverse=True
        )

        mensaje_usuarios = "Lista de usuarios inactivos:\n"

        for usuario_id, datos in usuarios_ordenados:
            if es_admin(int(usuario_id)) or es_bot(int(usuario_id)):
                continue  # Saltar a los administradores y bots

            mensajes = datos.get('numeroMensajes', 0)
            ultima_actividad_str = datos.get('ultimaActividad', None)
            if ultima_actividad_str:
                ultima_actividad = datetime.datetime.strptime(ultima_actividad_str, '%Y-%m-%d %H:%M:%S.%f')
                diferencia = datetime.datetime.now() - ultima_actividad

                if diferencia.days > 0:
                    mensaje_usuarios += f"- {datos['nombre']} NMensajes: {mensajes}, inactivo: {diferencia.days} días\n"
                elif diferencia.seconds // 3600 > 0:
                    mensaje_usuarios += f"- {datos['nombre']} NMensajes: {mensajes}, inactivo: {diferencia.seconds // 3600} horas\n"
                else:
                    mensaje_usuarios += f"- {datos['nombre']} NMensajes: {mensajes}, inactivo: {diferencia.seconds // 60} minutos\n"
            else:
                mensaje_usuarios += f"- {datos['nombre']} NMensajes: {mensajes}, inactividad desconocida\n"

        # Enviar la lista de usuarios inactivos en privado
        bot.send_message(message.chat.id, mensaje_usuarios)
    else:
        bot.reply_to(message, "No tienes permisos para ver la lista de inactivos.")


# Eliminar usuario del registro
def eliminar_usuario(usuario_id):
    usuario_id_str = str(usuario_id)  # Asegúrate de que el ID sea una cadena
    if usuario_id_str in usuarios:
        del usuarios[usuario_id_str]
        guardar_datos()

# Revisar inactividad
TIEMPO_INACTIVIDAD = 10080  # Tiempo de inactividad en minutos
def revisar_inactividad():
    while True:
        ahora = datetime.datetime.now()
        usuarios_para_expulsar = []

        for usuario_id, datos in list(usuarios.items()):
            if es_admin(int(usuario_id)) or es_bot(int(usuario_id)):
                continue  # Saltar a los administradores y bots

            ultima_actividad = datetime.datetime.strptime(datos['ultimaActividad'], '%Y-%m-%d %H:%M:%S.%f')
            diferencia = ahora - ultima_actividad
            if diferencia.total_seconds() >= TIEMPO_INACTIVIDAD * 60:
                usuarios_para_expulsar.append((usuario_id, datos['nombre']))

        for usuario_id, nombre in usuarios_para_expulsar:
            try:
                # Expulsar (kick) al usuario
                bot.kick_chat_member(chat_id, int(usuario_id))
                # Desbanear inmediatamente para permitir que vuelva a entrar
                bot.unban_chat_member(chat_id, int(usuario_id))
                eliminar_usuario(usuario_id)

                # Reiniciar el contador de mensajes de todos los usuarios
                reiniciar_mensajes()

            except Exception as e:
                print(f"No se pudo expulsar al usuario {nombre}. Error: {e}")

        # Revisar cada 2 minutos
        time.sleep(43200)

def reiniciar_mensajes():
    for usuario_id in usuarios:
        usuarios[usuario_id]['numeroMensajes'] = 0
    guardar_datos()


@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.chat.type == 'group' or message.chat.type == 'supergroup':
        usuario_id = message.from_user.id
        nombre = message.from_user.first_name
        agregar_o_actualizar_usuario(usuario_id, nombre)

        # Verificar si el usuario quiere activar el modo AFK
        texto = message.text.lower()

        # Si el texto comienza con 'brb' o 'afk', se pone el usuario en modo AFK
        if texto.startswith("brb") or texto.startswith("afk"):
            # Extraer el motivo después de "brb" o "afk"
            motivo_afk = texto.split(maxsplit=1)[1] if len(texto.split()) > 1 else "AFK"

            # Actualizar el estado AFK del usuario
            usuarios[str(usuario_id)]['AFK'] = True
            usuarios[str(usuario_id)]['motivoAFK'] = motivo_afk
            guardar_datos()

            # Enviar mensaje al grupo informando que el usuario está AFK
            bot.send_message(message.chat.id, f"{nombre} se fue <b>AFK</b>", parse_mode='HTML')

        else:
            # Si el usuario estaba AFK y ahora manda un mensaje, salir del estado AFK
            if usuarios[str(usuario_id)]['AFK']:
                ultima_actividad = datetime.datetime.strptime(usuarios[str(usuario_id)]['ultimaActividad'],
                                                              '%Y-%m-%d %H:%M:%S.%f')
                tiempo_afk = datetime.datetime.now() - ultima_actividad
                minutos_afk = tiempo_afk.seconds // 60
                horas_afk = minutos_afk // 60
                dias_afk = tiempo_afk.days

                # Salir del estado AFK
                usuarios[str(usuario_id)]['AFK'] = False
                usuarios[str(usuario_id)]['motivoAFK'] = None
                guardar_datos()

                # Determinar el formato de tiempo para el mensaje
                if dias_afk > 0:
                    horas_restantes = horas_afk % 24
                    bot.send_message(message.chat.id,
                                     f"<b>{nombre}</b> ha vuelto \nAFK: {dias_afk} días y {horas_restantes} horas.", parse_mode='HTML')
                elif horas_afk > 0:
                    minutos_restantes = minutos_afk % 60
                    bot.send_message(message.chat.id,
                                     f"<b>{nombre}</b> ha vuelto \nAFK: {horas_afk} horas y {minutos_restantes} minutos.", parse_mode='HTML')
                else:
                    bot.send_message(message.chat.id,
                                     f"<b>{nombre}</b> ha vuelto \nAFK: {minutos_afk} minutos.", parse_mode='HTML')

        if message.reply_to_message:
            usuario_respuesta_id = message.reply_to_message.from_user.id
            usuario_respuesta_nombre = message.reply_to_message.from_user.first_name

            # Verificar si el usuario al que se está respondiendo está en modo AFK
            if str(usuario_respuesta_id) in usuarios and usuarios[str(usuario_respuesta_id)].get('AFK', False):
                motivo_afk = usuarios[str(usuario_respuesta_id)]['motivoAFK']
                ultima_actividad_respuesta = datetime.datetime.strptime(
                    usuarios[str(usuario_respuesta_id)]['ultimaActividad'], '%Y-%m-%d %H:%M:%S.%f')
                tiempo_afk_respuesta = datetime.datetime.now() - ultima_actividad_respuesta
                minutos_afk_respuesta = tiempo_afk_respuesta.seconds // 60
                horas_afk_respuesta = minutos_afk_respuesta // 60
                dias_afk_respuesta = tiempo_afk_respuesta.days

                # Enviar mensaje informando que el usuario está AFK y por cuánto tiempo
                if dias_afk_respuesta > 0:
                    horas_restantes_respuesta = horas_afk_respuesta % 24
                    bot.send_message(message.chat.id,
                                     f"<b>{usuario_respuesta_nombre}</b> está <b>AFK</b> \nMotivo: <i>{motivo_afk}</i>. \nAFK {dias_afk_respuesta} días y {horas_restantes_respuesta} horas.", parse_mode='HTML')
                elif horas_afk_respuesta > 0:
                    minutos_restantes_respuesta = minutos_afk_respuesta % 60
                    bot.send_message(message.chat.id,
                                     f"<b>{usuario_respuesta_nombre}</b> está <b>AFK</b> \nMotivo: <i>{motivo_afk}</i>. \nAFK {horas_afk_respuesta} horas y {minutos_restantes_respuesta} minutos.", parse_mode='HTML')
                else:
                    bot.send_message(message.chat.id,
                                     f"<b>{usuario_respuesta_nombre}</b> está <b>AFK</b> \nMotivo: <i>{motivo_afk}</i>. \nAFK {minutos_afk_respuesta} minutos.", parse_mode='HTML')


@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_members(message):
    for member in message.new_chat_members:
        agregar_o_actualizar_usuario(member.id, member.first_name)
        #bot.send_message(message.chat.id, f"¡Hola {member.first_name}! ¡Bienvenido al grupo!")

@bot.message_handler(content_types=['left_chat_member'])
def goodbye_member(message):
    eliminar_usuario(message.left_chat_member.id)


if __name__ == "__main__":
    cargar_datos()

    # Iniciar un hilo para revisar la inactividad de los usuarios
    hilo_inactividad = threading.Thread(target=revisar_inactividad)
    hilo_inactividad.daemon = True
    hilo_inactividad.start()

    bot.polling(none_stop=True)
