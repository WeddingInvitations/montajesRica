# Instrucciones del proyecto Montajes Rica

- Aplicación Flask con plantillas Jinja, CSS y JavaScript vanilla; destino App Engine Standard con Python 3.11.
- Mantener la interfaz y documentación en español.
- No inventar nombres, resultados, divisiones o estadísticas reales. Los marcadores de `data/club.json` deben seguir claramente identificados como provisionales.
- No editar OWLManage ni copiar sus datos, credenciales o configuración privada.
- Usar Firebase Authentication con Google y verificar las sesiones/token criptográficamente mediante Firebase Admin SDK.
- Los usuarios nuevos son watcher por defecto; el rol admin se obtiene únicamente desde `users/{uid}` en Firestore y nunca de datos del cliente.
- Todas las escrituras Firestore deben requerir rol admin, validación de servidor y protección CSRF. El cliente web no accede directamente a Firestore.
- El listado de jugadores es información personal: no incluir el Excel ni nombres reales en Git; comprobar el alcance de acceso antes de importarlo a producción.
- No añadir integración SNP Galaxy sin comprobar API/acceso permitido con el usuario; no guardar sus credenciales.
- No añadir claves, contraseñas, tokens ni datos personales reales al repositorio.
- Ejecutar `python -m pytest` para validar cambios.
