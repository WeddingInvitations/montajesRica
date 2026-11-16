# Montajes Rica · Portal de pádel

Portal web en español para consultar los tres equipos del club (Masculino 500, Masculino Future y Femenino), sus plantillas, partidos/resultados y clasificaciones por división. La primera entrega es una **base visual y técnica**: los nombres de los equipos ya están configurados, pero divisiones y temporada siguen pendientes; no contiene jugadores, partidos ni clasificaciones reales, autenticación ni herramientas para editar datos desde la web.

La interfaz usa el logotipo `logoMontajes.jpeg`, una paleta carbón/cobre/crema inspirada en él y permite alternar entre tema claro y oscuro (la preferencia queda guardada en el navegador).

## Tecnologías

- Python 3.11, Flask y Gunicorn.
- HTML, CSS y JavaScript sin framework de frontend.
- Google App Engine Standard.
- Adaptador opcional de lectura de Firestore para el documento `club/current`.
- Cloud Build para desplegar App Engine.

La integración con SNP Galaxy queda expresamente aplazada. No se automatizan accesos ni se almacenan credenciales.

## Desarrollo local (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app app run --debug
```

Abre `http://127.0.0.1:5000`. La página usa los marcadores de `data/club.json`. Para ejecutar las pruebas:

```powershell
python -m pytest
```

## Estructura de datos

El documento de Firestore `club/current` puede tener estos campos:

- `club_name`, `season`
- `teams`: `id`, `name`, `division`, `season` (opcionalmente `color`)
- `players`: `id`, `name`, `team_id`, `handedness` (por ejemplo, `Drive` o `Revés`), `position` (opcional)
- `matches`: `id`, `team_id`, `opponent`, `date` (`YYYY-MM-DD`), `time`, `venue`, `home`, `score`, `status` (`scheduled` o `played`)
- `standings`: `division`, `season`, `position`, `team_name`, `played`, `wins`, `losses`, `points` y opcionalmente `is_club`

Los campos desconocidos se omiten o muestran como pendientes. No se deben cargar datos personales reales hasta haber configurado y probado autenticación/autorización para el portal. App Engine normalmente publica la aplicación; habilitar Firestore con datos de jugadores sin proteger el acceso no es seguro. El acceso del servidor a Firestore usa la cuenta de servicio de App Engine (ADC/IAM); no se incluyen claves JSON.

Para activar la lectura de Firestore, crear el documento y revisar primero el control de acceso, luego cambiar `USE_FIRESTORE` a `"true"` en `app.yaml`. En local se puede autenticar con `gcloud auth application-default login` y definir `GOOGLE_CLOUD_PROJECT`. App Engine necesita un rol IAM limitado a los datos que la aplicación lee (normalmente `roles/datastore.viewer`), además de estar en un proyecto con Firestore habilitado. Este portal todavía no escribe datos.

## Preparación manual en Google Cloud

El propietario del proyecto debe crear los recursos; el código no crea proyectos ni despliega automáticamente:

1. Crear un proyecto de GCP, asociar facturación y elegir las ubicaciones de App Engine y Firestore con cuidado: no suelen poder cambiarse después. Para empezar con coste bajo, App Engine usa instancia F1, cero instancias mínimas y máximo dos; Firestore cobra según uso y tiene cuotas/precios propios. Revisar la calculadora y activar alertas de presupuesto: las alertas no limitan el gasto.
2. Crear la aplicación de App Engine en la región elegida y habilitar Cloud Build. Habilitar Firestore solo cuando se vaya a usar.
3. Crear un repositorio privado de GitHub, subir este código y vincularlo a un trigger de Cloud Build (rama principal y configuración `cloudbuild.yaml`).
4. Asignar a la cuenta ejecutora del trigger permisos mínimos para desplegar App Engine (`roles/appengine.deployer` y `roles/iam.serviceAccountUser` sobre la cuenta runtime apropiada). Evitar roles amplios como Owner/Editor si la organización permite permisos más restringidos.
5. Configurar el acceso web antes de subir datos reales. No publicar datos de jugadores sin autenticación y autorización adecuadas. No almacenar tokens ni claves en Git; para secretos futuros, usar Secret Manager.

El trigger ejecutará `gcloud app deploy app.yaml --quiet`. La primera ejecución y el enlace del repositorio deben configurarse en la consola de GCP por el propietario del proyecto.

## Próximas decisiones

- Nombres de los tres equipos, divisiones y temporada.
- Fuente/hoja de cálculo con jugadores, partidos y resultados.
- Campos adicionales de la ficha (solo los necesarios; evitar información sensible).
- Quién puede consultar el portal y quién podrá administrar los datos.
- Diseño y política de acceso para implementar edición segura.
- Más adelante: comprobar las opciones oficiales de SNP Galaxy con autorización del titular de la cuenta; preferir API o exportación permitida y no guardar contraseñas.
