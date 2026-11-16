# Instrucciones del proyecto Montajes Rica

- Aplicación Flask con plantillas Jinja, CSS y JavaScript vanilla; destino App Engine Standard con Python 3.11.
- Mantener la interfaz y documentación en español.
- No inventar nombres, resultados, divisiones o estadísticas reales. Los marcadores de `data/club.json` deben seguir claramente identificados como provisionales.
- No editar OWLManage ni copiar sus datos, credenciales o configuración privada.
- En producción exigir Identity-Aware Proxy (IAP) y verificar criptográficamente su JWT; la lectura es para usuarios Google autenticados según el alcance elegido por el usuario.
- Todas las escrituras Firestore deben requerir rol admin, validación de servidor y protección CSRF. Nunca confiar en un correo de cabecera sin verificar el JWT de IAP.
- El listado de jugadores es información personal: no incluir el Excel ni nombres reales en Git; comprobar el alcance de acceso antes de importarlo a producción.
- No añadir integración SNP Galaxy sin comprobar API/acceso permitido con el usuario; no guardar sus credenciales.
- No añadir claves, contraseñas, tokens ni datos personales reales al repositorio.
- Ejecutar `python -m pytest` para validar cambios.
