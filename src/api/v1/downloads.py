import io
import zipfile
import tarfile
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.core.dependencies import CurrentActiveUser

router = APIRouter(prefix="/downloads", tags=["Downloads"])

SCRIPTS_BASE = Path("/home/erpnext/.services/scripts")

WINDOWS_FILES = [
    "SecurityMonitor.ps1",
    "MetricsCollector.ps1",
    "login_monitor.ps1",
    "config.example.ps1",
    "install.ps1",
]

LINUX_FILES = [
    "login_monitor.sh",
    "security_monitor.sh",
    "config.example.conf",
    "install.sh",
    "pibicyber-login.service",
    "pibicyber-login.timer",
    "pibicyber-monitor.service",
    "pibicyber-monitor.timer",
]

README_WINDOWS = """\
==========================================================
  PibiCyber Security Monitor - Agente Windows
  Generado: {date}
  API: {api_url}
==========================================================

INDICE
------
  1. Que hace este agente
  2. Requisitos
  3. Contenido del paquete
  4. Como obtener la API Key
  5. Instalacion paso a paso
  6. Configuracion detallada
  7. Verificar que funciona
  8. Ejecucion manual (pruebas)
  9. Logs y diagnostico
  10. Desinstalacion
  11. Solucion de problemas


1. QUE HACE ESTE AGENTE
------------------------
El agente Windows consta de dos scripts que se ejecutan en segundo plano
como tareas programadas de Windows y envian datos de seguridad a PibiCyber:

  SecurityMonitor.ps1
    Analiza el Registro de Eventos de Windows (Event Log) buscando:
    - Fallos de inicio de sesion (Event ID 4625)
    - Bloqueos de cuenta (Event ID 4740)
    - Usos de privilegios especiales (Event ID 4672)
    - Creacion/eliminacion de usuarios (Event IDs 4720, 4726)
    - Cambios de contrasena (Event IDs 4723, 4724)
    - Actividad de Windows Defender (detecciones de malware)
    - Intentos de login por RDP
    Se ejecuta una vez al dia (06:55) y al arrancar el sistema.
    Resultado: envia un evento de seguridad a la API con puntuacion de amenaza.

  MetricsCollector.ps1
    Recopila metricas del sistema cada 30 segundos de forma continua:
    - CPU: uso porcentual, frecuencia
    - RAM: usada, disponible, total
    - Disco: uso por unidad (C:, D:, etc.)
    - Red: bytes enviados/recibidos
    - Heartbeat a la API cada 60s para indicar que el agente esta activo
    Se inicia automaticamente al arrancar el sistema y corre de forma permanente.

  login_monitor.ps1
    Registra sesiones de usuario: inicios, cierres, sesiones RDP, cambios
    de cuenta. Se ejecuta junto con SecurityMonitor.


2. REQUISITOS
--------------
  - Windows 10 / Windows 11 / Windows Server 2016 o superior
  - PowerShell 5.1 o superior (incluido en Windows 10+)
  - Cuenta de Administrador para la instalacion
  - Conexion a internet para enviar datos a: {api_url}
  - Sin dependencias adicionales (no requiere instalar nada mas)

  Comprobacion de version de PowerShell (abrir PowerShell y ejecutar):
    $PSVersionTable.PSVersion


3. CONTENIDO DEL PAQUETE
-------------------------
  SecurityMonitor.ps1    Script principal de seguridad (Event Log)
  MetricsCollector.ps1   Script de metricas del sistema (loop continuo)
  login_monitor.ps1      Monitor de sesiones de usuario
  config.example.ps1     Plantilla de configuracion -> copiar a config.ps1
  install.ps1            Instalador automatico (Task Scheduler)


4. COMO OBTENER LA API KEY
---------------------------
La API Key es la contrasena secreta que identifica a este equipo ante
el servidor PibiCyber. Es unica para todos los agentes.

  Pasos:
  1. Abrir el dashboard: {api_url}
  2. Iniciar sesion con tu usuario administrador
  3. Ir a Configuracion > Instalacion Agentes
  4. Copiar el valor del campo "API Key de Agente"

  IMPORTANTE: Esta clave es compartida entre todos los agentes.
  Mantenerla en secreto y no compartirla publicamente.


5. INSTALACION PASO A PASO
---------------------------

  PASO 1 - Crear la carpeta de instalacion
  -----------------------------------------
  Abre PowerShell como Administrador (clic derecho > "Ejecutar como administrador")
  y ejecuta:

    New-Item -ItemType Directory -Force -Path "C:\\PibiCyber"

  Copia todos los archivos de este paquete a C:\\PibiCyber\\
  (puedes arrastrarlos con el Explorador de archivos)

  PASO 2 - Crear el archivo de configuracion
  -------------------------------------------
  En PowerShell (como Administrador), ejecuta:

    Copy-Item "C:\\PibiCyber\\config.example.ps1" "C:\\PibiCyber\\config.ps1"
    notepad "C:\\PibiCyber\\config.ps1"

  Se abrira el Bloc de notas. Edita SOLO estas tres lineas:

    $API_URL      = "https://raquel.pibico.es"    <- URL del servidor (sin /cyber al final)
    $API_ROOT_PATH = "/cyber"                      <- No cambiar normalmente
    $API_KEY      = "pega-aqui-tu-api-key"        <- La clave obtenida en el paso 4

  El AGENT_ID (nombre del equipo) se toma automaticamente del nombre del PC.
  Si quieres un nombre personalizado, descomenta y edita esta linea:
    # $AGENT_ID = "mi-portatil"  ->  $AGENT_ID = "PORTATIL-PIBICO"

  Guarda y cierra el Bloc de notas.

  PASO 3 - Configurar la politica de ejecucion de PowerShell
  ------------------------------------------------------------
  Windows bloquea por defecto la ejecucion de scripts. Ejecuta:

    Set-ExecutionPolicy -Scope LocalMachine RemoteSigned -Force

  Esto permite ejecutar scripts locales firmados. Es necesario una sola vez.

  PASO 4 - Ejecutar el instalador
  ---------------------------------
  En PowerShell como Administrador:

    cd "C:\\PibiCyber"
    .\\install.ps1

  El instalador creara dos tareas en el Programador de Tareas de Windows:
    - PibiCyber-SecurityMonitor: se ejecuta diariamente a las 06:55 y al arrancar
    - PibiCyber-MetricsCollector: se inicia al arrancar y corre de forma permanente

  PASO 5 - Iniciar los agentes por primera vez (sin reiniciar)
  --------------------------------------------------------------
  Sin necesidad de reiniciar el PC, inicia las tareas manualmente:

    Start-ScheduledTask -TaskName "PibiCyber-SecurityMonitor"
    Start-ScheduledTask -TaskName "PibiCyber-MetricsCollector"

  El agente de metricas tardara unos 10-15 segundos en aparecer como activo
  en el dashboard.


6. CONFIGURACION DETALLADA
---------------------------
  Abre C:\\PibiCyber\\config.ps1 para ver o cambiar la configuracion.

  Variable          Obligatoria  Descripcion
  ----------------  -----------  ---------------------------------------------------
  $API_URL          SI           URL base del servidor. Ej: "https://raquel.pibico.es"
                                 Sin barra al final, sin /cyber
  $API_ROOT_PATH    SI           Prefijo de la API. Normalmente "/cyber". No cambiar.
  $API_KEY          SI           Clave secreta del agente. Obtenida del dashboard.
  $AGENT_ID         NO           Nombre del equipo en el dashboard. Por defecto usa
                                 el nombre del PC (hostname). Cambiar solo si quieres
                                 un nombre mas descriptivo. Ej: "PORTATIL-PIBICO"
  $LOG_HOURS        NO           Horas de historial a analizar. Por defecto: 24
  $WHITELIST_IPS    NO           IPs a ignorar en el analisis. Ej: @("192.168.1.1")
                                 Util para IPs de red interna que no son amenazas.
  $ALERT_WEBHOOK    NO           URL de webhook para alertas criticas inmediatas.
                                 Compatible con Slack, Teams, Discord.
  $ALERT_THRESHOLD  NO           Puntuacion minima para enviar alerta. Por defecto: 100


7. VERIFICAR QUE FUNCIONA
--------------------------
  Opcion A - Desde el dashboard:
    Abrir {api_url} e ir a la seccion "Agentes".
    Este equipo deberia aparecer como activo en 1-2 minutos
    tras iniciar MetricsCollector.

  Opcion B - Desde PowerShell:
    Ver estado de las tareas:
      Get-ScheduledTask -TaskName "PibiCyber-*" | Select TaskName, State

    Ver si MetricsCollector esta corriendo:
      Get-ScheduledTask -TaskName "PibiCyber-MetricsCollector" | Select -Expand TaskPath

    Ver los logs en tiempo real:
      Get-Content "C:\\PibiCyber\\logs\\metrics_collector.log" -Tail 20
      Get-Content "C:\\PibiCyber\\logs\\monitor.log" -Tail 20

  Una entrada correcta en el log de metricas tiene este aspecto:
    [2026-02-25 10:30:15] [INFO] Heartbeat enviado correctamente
    [2026-02-25 10:30:15] [INFO] Metricas enviadas correctamente (24 metricas)


8. EJECUCION MANUAL (para pruebas)
------------------------------------
  Si quieres ejecutar los scripts directamente (sin Task Scheduler):

  Abrir PowerShell como Administrador:
    cd "C:\\PibiCyber"

  SecurityMonitor (analisis de seguridad, tarda 1-2 min):
    .\\SecurityMonitor.ps1

  MetricsCollector (loop continuo, Ctrl+C para detener):
    .\\MetricsCollector.ps1

  ATENCION: MetricsCollector es un proceso continuo. En ejecucion manual
  el terminal quedara bloqueado hasta que lo detengas con Ctrl+C.


9. LOGS Y DIAGNOSTICO
----------------------
  Ubicacion de los logs:
    C:\\PibiCyber\\logs\\monitor.log             <- SecurityMonitor y login_monitor
    C:\\PibiCyber\\logs\\metrics_collector.log   <- MetricsCollector

  Ver las ultimas 50 lineas de un log:
    Get-Content "C:\\PibiCyber\\logs\\monitor.log" -Tail 50

  Seguir el log en tiempo real:
    Get-Content "C:\\PibiCyber\\logs\\metrics_collector.log" -Wait -Tail 20

  Niveles de log:
    [INFO]  Operacion normal
    [WARN]  Aviso (p.ej. fallo al conectar, se reintentara)
    [ERROR] Error grave


10. DESINSTALACION
------------------
  Para eliminar completamente el agente:

  Paso 1 - Detener y eliminar las tareas programadas:
    Stop-ScheduledTask -TaskName "PibiCyber-MetricsCollector" -ErrorAction SilentlyContinue
    Get-ScheduledTask -TaskName "PibiCyber-*" | Unregister-ScheduledTask -Confirm:$false

  Paso 2 - Eliminar los archivos (opcional):
    Remove-Item -Recurse -Force "C:\\PibiCyber"

  Paso 3 - El agente aparecera como inactivo en el dashboard en ~25 horas.
           Para eliminarlo inmediatamente, borrarlo desde Configuracion > Agentes.


11. SOLUCION DE PROBLEMAS
--------------------------
  Problema: El agente no aparece en el dashboard
    Causa:   config.ps1 tiene API_URL o API_KEY incorrectos
    Solucion: Revisar el log: Get-Content "C:\\PibiCyber\\logs\\metrics_collector.log" -Tail 20
              Buscar lineas con [WARN] o [ERROR].
              Ejecutar manualmente para ver el error en pantalla:
                cd "C:\\PibiCyber"; .\\MetricsCollector.ps1

  Problema: Error "execution of scripts is disabled on this system"
    Causa:   La politica de ejecucion de PowerShell esta restringida
    Solucion: Abrir PowerShell como Administrador y ejecutar:
                Set-ExecutionPolicy -Scope LocalMachine RemoteSigned -Force

  Problema: Error "Access Denied" o "privileges required"
    Causa:   PowerShell no esta corriendo como Administrador
    Solucion: Clic derecho en PowerShell > "Ejecutar como administrador"

  Problema: Las tareas existen pero el agente sale como inactivo
    Causa:   MetricsCollector puede haber fallado al iniciarse
    Solucion: Ver log de errores y reiniciar la tarea:
                Stop-ScheduledTask -TaskName "PibiCyber-MetricsCollector"
                Start-ScheduledTask -TaskName "PibiCyber-MetricsCollector"

  Problema: El SecurityMonitor no envia datos
    Causa:   Puede necesitar permisos para leer el Security Event Log
    Solucion: La tarea usa la cuenta SYSTEM que tiene acceso completo.
              Verificar que la tarea esta configurada con cuenta SYSTEM:
                Get-ScheduledTask -TaskName "PibiCyber-SecurityMonitor" |
                  Select -Expand Principal

  Problema: "Unable to connect" o timeout al conectar con la API
    Causa:   Firewall, proxy, o la URL de la API es incorrecta
    Solucion: Probar conectividad:
                Invoke-WebRequest -Uri "{api_url}/health" -UseBasicParsing
              Si falla, comprobar configuracion de red o proxy corporativo.

==========================================================
  Dashboard: {api_url}
  Generado automaticamente por PibiCyber
==========================================================
"""

README_LINUX = """\
==========================================================
  PibiCyber Security Monitor - Agente Linux
  Generado: {date}
  API: {api_url}
==========================================================

INDICE
------
  1. Que hace este agente
  2. Requisitos y dependencias
  3. Contenido del paquete
  4. Como obtener la API Key
  5. Instalacion paso a paso
  6. Configuracion detallada
  7. Verificar que funciona
  8. Ejecucion manual (pruebas)
  9. Logs y diagnostico
  10. Desinstalacion
  11. Solucion de problemas


1. QUE HACE ESTE AGENTE
------------------------
El agente Linux se compone de dos scripts que se ejecutan periodicamente
y envian eventos de seguridad a PibiCyber:

  security_monitor.sh
    Analiza los logs del sistema buscando amenazas de seguridad:
    - SSH: intentos de acceso fallidos, usuarios invalidos, IPs bloqueadas
    - Nginx: peticiones a rutas sospechosas (admin, .env, wp-admin, etc.)
    - Firewall (ufw/iptables): paquetes bloqueados por reglas
    - Sudo/su: fallos de autenticacion, escalada de privilegios
    - Servicios: caidas de servicios criticos del sistema
    Calcula una puntuacion de amenaza y banea IPs automaticamente si supera
    el umbral configurado.
    Frecuencia: una vez al dia (07:55 AM por defecto via cron).
    Resultado: envia un evento con todos los hallazgos a la API.

  login_monitor.sh
    Registra la actividad de inicio de sesion:
    - Logins exitosos y fallidos (SSH, consola, PAM)
    - Uso de sudo y comandos ejecutados como root
    - Anomalias: multiples intentos desde la misma IP (brute force)
    Frecuencia: configurable, por defecto no se instala por separado.

  NOTA: El instalador automatico (install.sh) solo configura security_monitor.sh
  en cron. login_monitor.sh puede ejecutarse manualmente o anadir al cron.


2. REQUISITOS Y DEPENDENCIAS
------------------------------
  Sistema operativo:
    - Debian 10+ / Ubuntu 20.04+ / Rocky Linux 8+ / CentOS 8+
    - Cualquier distribucion Linux con bash 4.0 y systemd o cron

  Herramientas requeridas (normalmente ya instaladas):
    - bash 4.0 o superior
    - curl     (para enviar datos a la API)
    - jq       (para procesar JSON)
    - awk, grep, sed (herramientas de texto estandar)
    - ss       (para listar conexiones de red, alternativa: netstat)

  Instalar dependencias en Debian/Ubuntu:
    sudo apt-get update && sudo apt-get install -y curl jq

  Instalar dependencias en RHEL/Rocky/CentOS:
    sudo yum install -y curl jq

  Permisos:
    - Se necesita sudo o root para la instalacion y para leer ciertos logs
    - Los scripts deben ejecutarse como root (o con sudo) para acceder
      a /var/log/auth.log, /var/log/syslog, registros de nginx, etc.


3. CONTENIDO DEL PAQUETE
-------------------------
  security_monitor.sh    Script principal de seguridad (analisis de logs)
  login_monitor.sh       Monitor de actividad de logins y sudo
  config.example.conf    Plantilla de configuracion -> copiar a config.conf
  install.sh             Instalador automatico via cron


4. COMO OBTENER LA API KEY
---------------------------
La API Key es la clave secreta que identifica a este servidor ante PibiCyber.
Es la misma para todos los agentes (Linux y Windows).

  Pasos:
  1. Abrir el dashboard en un navegador: {api_url}
  2. Iniciar sesion con tu usuario administrador
  3. Ir a Configuracion > Instalacion Agentes
  4. Copiar el valor del campo "API Key de Agente"

  IMPORTANTE: Esta clave es secreta. No la compartas ni la subas a git.
  El archivo config.conf debe tener permisos 600 (solo lectura por root).


5. INSTALACION PASO A PASO
---------------------------

  PASO 1 - Crear la carpeta e copiar los archivos
  -------------------------------------------------
  Conéctate al servidor como root o con sudo y ejecuta:

    sudo mkdir -p /opt/pibicyber
    sudo cp * /opt/pibicyber/
    sudo chmod +x /opt/pibicyber/*.sh

  Si descargaste el tar.gz desde el dashboard, extrae con:
    tar -xzf pibicyber-scripts-linux.tar.gz
    sudo cp pibicyber-linux/* /opt/pibicyber/
    sudo chmod +x /opt/pibicyber/*.sh

  PASO 2 - Crear el archivo de configuracion
  -------------------------------------------
    sudo cp /opt/pibicyber/config.example.conf /opt/pibicyber/config.conf
    sudo nano /opt/pibicyber/config.conf

  Edita las siguientes lineas (las demas son opcionales):

    API_URL="https://raquel.pibico.es"   <- URL del servidor (sin /cyber al final)
    API_ROOT_PATH="/cyber"               <- No cambiar normalmente
    API_KEY="pega-aqui-tu-api-key"      <- La clave obtenida en el paso 4

  El AGENT_ID se toma del hostname por defecto. Si quieres un nombre
  personalizado para este servidor en el dashboard, descomenta:
    # AGENT_ID="servidor-web-01"  ->  AGENT_ID="raquelserver"

  Guarda los cambios (en nano: Ctrl+O, Enter, Ctrl+X) y protege el archivo:
    sudo chmod 600 /opt/pibicyber/config.conf

  PASO 3 - Ejecutar el instalador
  ---------------------------------
    sudo bash /opt/pibicyber/install.sh

  El instalador:
  - Verifica que existe config.conf y que tiene permiso 600
  - Marca security_monitor.sh como ejecutable
  - Anade una entrada en el cron del usuario actual:
      55 7 * * * /opt/pibicyber/security_monitor.sh
    (se ejecutara todos los dias a las 07:55)
  - Informa de cualquier problema encontrado

  PASO 4 - Primera ejecucion para verificar la conexion
  -------------------------------------------------------
  Sin esperar al cron, ejecuta el script manualmente para confirmar
  que la configuracion es correcta:

    sudo bash /opt/pibicyber/security_monitor.sh

  Si todo va bien, veras en la salida algo como:
    [INFO] Heartbeat enviado correctamente (HTTP 200)
    [INFO] Reporte enviado correctamente

  Y el servidor aparecera en el dashboard de PibiCyber como agente activo.


6. CONFIGURACION DETALLADA
---------------------------
  Abre /opt/pibicyber/config.conf para ver o cambiar la configuracion.

  Variable          Obligatoria  Descripcion
  ----------------  -----------  ---------------------------------------------------
  API_URL           SI           URL base del servidor. Ej: "https://raquel.pibico.es"
                                 Sin barra al final y sin /cyber
  API_ROOT_PATH     SI           Prefijo de la API. Normalmente "/cyber". No cambiar.
  API_KEY           SI           Clave secreta del agente. Obtenida del dashboard.
  AGENT_ID          NO           Nombre del servidor en el dashboard. Por defecto
                                 usa el hostname del sistema. Cambiar si quieres
                                 un nombre mas descriptivo. Ej: "servidor-produccion"
  LOG_HOURS         NO           Horas de historial de logs a analizar. Por defecto: 24
                                 Reducir si el servidor tiene muchos logs.
  WHITELIST_IPS     NO           IPs separadas por comas a ignorar en el analisis.
                                 Ej: "192.168.1.1,10.0.0.5"
                                 Util para IPs de monitorizacion, backups, VPN, etc.
  ALERT_WEBHOOK     NO           URL de webhook para alertas criticas inmediatas.
                                 Compatible con Slack, Discord, Teams.
                                 Ej: "https://hooks.slack.com/services/xxx"
  ALERT_THRESHOLD   NO           Puntuacion de amenaza minima para enviar alerta.
                                 Por defecto: 100. Bajar para alertas mas frecuentes.


7. VERIFICAR QUE FUNCIONA
--------------------------
  Opcion A - Desde el dashboard:
    Abrir {api_url} e ir a la seccion "Agentes".
    El servidor deberia aparecer como activo tras la primera ejecucion.

  Opcion B - Desde la terminal:
    Ver el cron configurado:
      crontab -l | grep pibicyber

    Comprobar el log tras una ejecucion:
      tail -30 /opt/pibicyber/logs/monitor.log

    Una ejecucion correcta termina con:
      [INFO] Heartbeat enviado correctamente (HTTP 200)
      [INFO] Reporte enviado correctamente

  Opcion C - Probar la conexion con la API manualmente:
    curl -s {api_url}/api/v1/health


8. EJECUCION MANUAL (para pruebas)
------------------------------------
  Ejecutar security_monitor.sh (muestra el JSON generado en pantalla):
    sudo bash /opt/pibicyber/security_monitor.sh

  Ejecutar solo login_monitor:
    sudo bash /opt/pibicyber/login_monitor.sh

  Ver lo que enviaria sin enviarlo (dry run - editar script para activar):
    El script genera el JSON completo antes de enviarlo. Se puede ver
    en la salida estandar o en los archivos en:
      /opt/pibicyber/logs/

  NOTA: El script tiene proteccion anti-duplicado. Si ya se ejecuto hoy,
  mostrara "Ya existe un reporte de hoy. Saltando ejecucion." y terminara.
  Para forzar una nueva ejecucion en el mismo dia, eliminar el archivo:
    rm /home/erpnext/.services/scripts/json/linux/report_$(date +%Y-%m-%d)*.json
  (Ajusta la ruta segun donde hayas instalado los scripts)


9. LOGS Y DIAGNOSTICO
----------------------
  Ubicacion de los logs (dentro de la carpeta de instalacion):
    /opt/pibicyber/logs/monitor.log         <- security_monitor.sh
    /opt/pibicyber/logs/login_monitor.log   <- login_monitor.sh

  Ver las ultimas 30 lineas:
    tail -30 /opt/pibicyber/logs/monitor.log

  Seguir el log en tiempo real durante una ejecucion:
    tail -f /opt/pibicyber/logs/monitor.log

  Niveles de log:
    [INFO]  Operacion completada con exito
    [WARN]  Aviso no critico (p.ej. fallo temporal de conexion)
    [ERROR] Error que impide continuar

  JSON enviados (para depuracion):
    Los JSON completos que se envian a la API se guardan en:
    /opt/pibicyber/logs/ (o en la subcarpeta json/)
    Util para verificar exactamente que datos se estan enviando.


10. DESINSTALACION
------------------
  Paso 1 - Eliminar la entrada del cron:
    crontab -l | grep -v "pibicyber" | crontab -

  Paso 2 - Verificar que se elimino:
    crontab -l

  Paso 3 - Eliminar los archivos (opcional):
    sudo rm -rf /opt/pibicyber/

  Paso 4 - El agente aparecera como inactivo en el dashboard en ~25 horas.
           Para eliminarlo inmediatamente, borrarlo desde la seccion Agentes.


11. SOLUCION DE PROBLEMAS
--------------------------
  Problema: El agente no aparece en el dashboard tras ejecutar el script
    Causa:   API_URL o API_KEY incorrectos en config.conf
    Solucion: Revisar el log:
                tail -20 /opt/pibicyber/logs/monitor.log
              Buscar lineas [WARN] o [ERROR].
              Probar la URL directamente:
                curl -v {api_url}/api/v1/health

  Problema: "jq: command not found" o "curl: command not found"
    Causa:   Dependencias no instaladas
    Solucion: sudo apt-get install -y curl jq  (Debian/Ubuntu)
              sudo yum install -y curl jq       (RHEL/CentOS/Rocky)

  Problema: "Permission denied" al leer logs del sistema
    Causa:   El script no se ejecuta como root o sudo
    Solucion: sudo bash /opt/pibicyber/security_monitor.sh
              Para el cron, asegurarse de que crontab -l muestra la entrada
              en el crontab de root: sudo crontab -l

  Problema: "config.conf: Permission denied" o "600 requerido"
    Causa:   Permisos del archivo de configuracion
    Solucion: sudo chmod 600 /opt/pibicyber/config.conf
              sudo chown root:root /opt/pibicyber/config.conf

  Problema: "Ya existe un reporte de hoy. Saltando ejecucion."
    Causa:   El script ya se ejecuto hoy y tiene proteccion anti-duplicado
    Solucion: Comportamiento normal. Si necesitas forzar otra ejecucion,
              eliminar el archivo de marca del dia actual (ver seccion 8).

  Problema: El script se ejecuta pero no aparece en "Agentes" del dashboard
    Causa:   Puede que el heartbeat falle pero el script continue
    Solucion: Buscar en el log la linea "Heartbeat enviado":
                grep "Heartbeat\|HTTP" /opt/pibicyber/logs/monitor.log | tail -5
              Si muestra HTTP 401: la API_KEY es incorrecta
              Si muestra HTTP 404: la API_URL o API_ROOT_PATH son incorrectos
              Si no hay respuesta: problema de red o firewall

  Problema: El cron no ejecuta el script automaticamente
    Causa:   El cron puede no estar activo o la ruta es incorrecta
    Solucion: Verificar que cron esta corriendo:
                sudo systemctl status cron   (Debian/Ubuntu)
                sudo systemctl status crond  (RHEL/Rocky)
              Ver el cron del usuario actual:
                crontab -l
              Nota: el instalador add el cron al usuario que lo ejecuta.
              Si instalaste con sudo, el cron queda en el usuario sudo,
              no en root. Para instalarlo en root: sudo crontab -e

==========================================================
  Dashboard: {api_url}
  Generado automaticamente por PibiCyber
==========================================================
"""


def _detect_os(user_agent: str) -> str:
    ua = user_agent.lower()
    if "windows" in ua:
        return "windows"
    return "linux"


def _build_windows_zip() -> io.BytesIO:
    buf = io.BytesIO()
    scripts_dir = SCRIPTS_BASE / "windows"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        readme = README_WINDOWS.format(
            date=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            api_url="https://raquel.pibico.es/cyber",
        )
        zf.writestr("pibicyber-windows/README.txt", readme)
        for filename in WINDOWS_FILES:
            filepath = scripts_dir / filename
            if filepath.exists():
                zf.write(filepath, f"pibicyber-windows/{filename}")
    buf.seek(0)
    return buf


def _build_linux_targz() -> io.BytesIO:
    buf = io.BytesIO()
    scripts_dir = SCRIPTS_BASE / "linux"
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        readme = README_LINUX.format(
            date=datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            api_url="https://raquel.pibico.es/cyber",
        )
        readme_bytes = readme.encode("utf-8")
        info = tarfile.TarInfo(name="pibicyber-linux/README.txt")
        info.size = len(readme_bytes)
        tf.addfile(info, io.BytesIO(readme_bytes))
        for filename in LINUX_FILES:
            filepath = scripts_dir / filename
            if filepath.exists():
                tf.add(filepath, arcname=f"pibicyber-linux/{filename}")
    buf.seek(0)
    return buf


@router.get("/scripts")
async def download_scripts(
    request: Request,
    current_user: CurrentActiveUser,
):
    """Download monitoring scripts bundle for client OS (Windows ZIP / Linux tar.gz)."""
    user_agent = request.headers.get("user-agent", "")
    detected_os = _detect_os(user_agent)

    if detected_os == "windows":
        buf = _build_windows_zip()
        filename = "pibicyber-scripts-windows.zip"
        media_type = "application/zip"
    else:
        buf = _build_linux_targz()
        filename = "pibicyber-scripts-linux.tar.gz"
        media_type = "application/gzip"

    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/scripts/info")
async def get_scripts_info(
    request: Request,
    current_user: CurrentActiveUser,
):
    """Return detected OS and available scripts list."""
    user_agent = request.headers.get("user-agent", "")
    detected_os = _detect_os(user_agent)

    if detected_os == "windows":
        scripts_dir = SCRIPTS_BASE / "windows"
        files = WINDOWS_FILES
        package = "pibicyber-scripts-windows.zip"
    else:
        scripts_dir = SCRIPTS_BASE / "linux"
        files = LINUX_FILES
        package = "pibicyber-scripts-linux.tar.gz"

    available = [f for f in files if (scripts_dir / f).exists()]
    return {
        "detected_os": detected_os,
        "package_name": package,
        "scripts": available,
    }
