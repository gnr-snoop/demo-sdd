# PRD: Face Insight Demo

**Estado:** Propuesto  
**Versión:** 1.0  
**Tipo de producto:** Demo web de autenticación y análisis facial  
**Audiencia principal:** Equipo de desarrollo y audiencia de la demo  
**Última actualización:** 2026-08-31

## 1. Resumen ejecutivo

Face Insight Demo es una aplicación web que permite a una persona registrarse mediante una captura de su rostro, iniciar sesión posteriormente utilizando el rostro registrado y, una vez autenticada, acceder a una pantalla protegida con la cámara activa.

Dentro de esa pantalla, la persona podrá solicitar dos análisis bajo demanda:

- Detección del estado de ánimo.
- Estimación de edad.

La aplicación tiene un objetivo demostrativo y educativo: mostrar un flujo completo de frontend, backend y procesamiento de visión por computadora siguiendo un workflow de desarrollo basado en specs. No pretende ser un sistema de identificación biométrica para producción ni un instrumento de vigilancia o toma de decisiones de alto impacto.

## 2. Problema y oportunidad

Las demos de visión por computadora suelen mostrar únicamente un modelo aislado o una interfaz sin flujo de producto completo. Este proyecto busca demostrar cómo integrar capacidades de visión facial en una experiencia sencilla y entendible:

1. Una persona crea su perfil.
2. El sistema registra una representación de su rostro.
3. La persona vuelve a identificarse con la cámara.
4. La aplicación le permite ejecutar análisis faciales desde una pantalla autenticada.

El valor de la demo está en el flujo integrado y en las decisiones de producto, seguridad y arquitectura, no en ofrecer precisión clínica o biométrica certificada.

## 3. Objetivos

### 3.1 Objetivos del MVP

- Permitir el onboarding de una persona con un identificador básico y una captura facial.
- Validar que la captura de onboarding contiene exactamente un rostro utilizable.
- Guardar una plantilla o embedding facial asociado a la persona.
- Permitir el login mediante una nueva captura del rostro.
- Crear una sesión autenticada tras una verificación facial exitosa.
- Mostrar una pantalla protegida con la cámara del dispositivo.
- Permitir ejecutar manualmente un análisis de estado de ánimo.
- Permitir ejecutar manualmente una estimación de edad.
- Mostrar estados claros de carga, éxito y error.
- Mantener separada la lógica de negocio de los adaptadores concretos de YOLO y de los modelos de análisis.

### 3.2 Objetivos de la demo

- Ser ejecutable localmente con instrucciones simples.
- Poder demostrar el flujo completo en pocos minutos.
- Permitir reemplazar implementaciones mock por modelos reales sin rediseñar el flujo de usuario.
- Hacer explícitas las limitaciones de los resultados de edad y estado de ánimo.

## 4. No objetivos

El MVP no incluirá:

- Identificación de una persona entre múltiples usuarios a partir únicamente del rostro, es decir, reconocimiento 1:N.
- Vigilancia continua o análisis de video sin una acción explícita de la persona.
- Detección de vida o protección antifraude avanzada.
- Reconocimiento de emociones con validez clínica o psicológica.
- Uso de los resultados para decisiones laborales, crediticias, médicas, legales o similares.
- Soporte multi-tenant o administración avanzada de usuarios.
- Aplicación móvil nativa.
- Persistencia de video continuo.
- Panel administrativo.
- Recuperación de cuenta, cambio de contraseña o autenticación multifactor.
- Garantía de precisión para todas las condiciones de iluminación, cámaras, edades o grupos demográficos.

## 5. Usuarios y actores

### 5.1 Persona usuaria

Persona que se registra, inicia sesión con su rostro y solicita análisis desde la pantalla autenticada.

### 5.2 Servicio de análisis facial

Componente backend que recibe una captura puntual, detecta el rostro y ejecuta el análisis solicitado.

### 5.3 Modelo de detección

Modelo basado en YOLO o un adaptador equivalente utilizado para localizar rostros en una imagen. YOLO se considera el detector, no necesariamente el modelo de reconocimiento de identidad ni el modelo de estimación de edad o estado de ánimo.

## 6. Experiencia de usuario

### 6.1 Navegación principal

La aplicación tendrá las siguientes vistas:

```text
/                 Página de bienvenida
/onboarding       Registro facial
/login            Login facial
/dashboard        Cámara y análisis, requiere sesión
```

El acceso a `/dashboard` sin una sesión válida debe redirigir a `/login`.

### 6.2 Flujo de onboarding

1. La persona accede a la página de onboarding.
2. Introduce un identificador, inicialmente un email o username.
3. Acepta el consentimiento para el procesamiento de datos biométricos y faciales.
4. Concede permiso para utilizar la cámara.
5. Ve la previsualización de la cámara.
6. Pulsa el botón de captura.
7. El frontend envía una imagen puntual al backend.
8. El backend valida la imagen y genera la plantilla facial.
9. El sistema confirma que el onboarding finalizó correctamente.
10. La persona puede ir a la pantalla de login.

### Estados de onboarding

- Inicial: formulario y botón de inicio de cámara.
- Solicitando permiso: el navegador está solicitando acceso a la cámara.
- Cámara no disponible: permiso denegado, dispositivo sin cámara o error del navegador.
- Listo para capturar: se muestra la previsualización.
- Procesando: la captura está siendo validada y procesada.
- Éxito: el perfil facial fue creado.
- Error recuperable: se solicita corregir la captura o repetir el proceso.

### 6.3 Flujo de login facial

1. La persona accede a `/login`.
2. Introduce el mismo identificador utilizado durante el onboarding.
3. Concede permiso para utilizar la cámara, si todavía no lo hizo.
4. Captura una nueva imagen de su rostro.
5. El frontend envía el identificador y la captura al backend.
6. El backend obtiene la plantilla registrada para ese identificador.
7. El backend compara el rostro capturado con la plantilla.
8. Si la similitud supera el umbral configurado, crea una sesión.
9. La persona es redirigida a `/dashboard`.

Si la comparación falla, no se crea una sesión y se muestra un mensaje genérico que permita reintentar.

### Decisión de alcance: verificación 1:1

El login del MVP es una verificación 1:1: la persona declara su identificador y el sistema comprueba si el rostro corresponde a ese registro. No se buscará el rostro contra todos los usuarios registrados.

### 6.4 Dashboard autenticado

La pantalla protegida debe contener:

- Indicador de que la sesión está activa.
- Previsualización de la cámara.
- Botón `Detectar estado de ánimo`.
- Botón `Calcular edad`.
- Resultado más reciente del análisis de estado de ánimo.
- Resultado más reciente de la estimación de edad.
- Indicadores de carga independientes para cada operación.
- Mensaje de error recuperable para cada operación.
- Botón de cierre de sesión.

Cada botón debe generar una captura puntual en el momento de la acción. El sistema no ejecutará análisis automáticamente en cada frame de video.

### Resultado de estado de ánimo

El resultado se mostrará como una categoría legible para la persona, por ejemplo `neutral`, `feliz`, `triste`, `sorprendido` o `no concluyente`, acompañada opcionalmente por una confianza presentada como valor aproximado.

La interfaz debe comunicar que se trata de una inferencia del modelo y no de una medición objetiva del estado emocional real.

### Resultado de edad

El resultado se mostrará como una edad estimada en años o, preferentemente, como un rango de edad si el modelo lo permite.

La interfaz debe comunicar que el valor es una estimación visual y puede tener un margen de error relevante.

## 7. Requisitos funcionales

### FR-001: Crear perfil facial

El sistema debe permitir crear un perfil con un identificador único y una plantilla facial derivada de una captura válida.

### FR-002: Validar identificador

El sistema debe rechazar identificadores vacíos, con formato inválido o ya registrados.

### FR-003: Solicitar consentimiento

El sistema debe requerir una aceptación explícita antes de capturar o procesar una imagen facial.

### FR-004: Validar captura facial

El backend debe rechazar una captura que:

- No contenga ningún rostro.
- Contenga más de un rostro.
- No tenga calidad suficiente para el modelo configurado.
- No pueda ser decodificada o tenga un formato no soportado.

### FR-005: Detectar rostro

El sistema debe utilizar un detector facial basado en YOLO, o un adaptador mock durante la etapa inicial, para localizar el rostro en la captura.

### FR-006: Generar plantilla facial

El sistema debe convertir el rostro detectado en una representación comparable, como un embedding, y asociarla al perfil.

### FR-007: Iniciar sesión con el rostro

El sistema debe permitir verificar el rostro de una persona contra la plantilla asociada al identificador proporcionado.

### FR-008: Aplicar umbral de similitud

El sistema debe aceptar o rechazar la verificación según un umbral configurable. El umbral no debe estar fijado únicamente en el frontend.

### FR-009: Crear sesión

El sistema debe crear una sesión únicamente después de una verificación facial exitosa.

### FR-010: Proteger dashboard

El sistema debe impedir el acceso a `/dashboard` y a sus endpoints si no existe una sesión válida.

### FR-011: Capturar imagen puntual

El dashboard debe permitir capturar una imagen puntual desde la cámara al pulsar cualquiera de los botones de análisis.

### FR-012: Detectar estado de ánimo

El sistema debe procesar la captura y devolver una categoría de estado de ánimo y, si está disponible, una confianza o indicador de calidad.

### FR-013: Calcular edad

El sistema debe procesar la captura y devolver una edad estimada o un rango de edad.

### FR-014: Evitar acciones simultáneas inválidas

El frontend debe deshabilitar el botón correspondiente mientras su análisis está en curso. La política para permitir o no el otro análisis simultáneamente debe ser explícita; para el MVP se recomienda procesar una captura a la vez.

### FR-015: Mostrar errores accionables

Los errores deben indicar una acción posible, por ejemplo repetir la captura, revisar el permiso de cámara o volver a iniciar sesión, sin exponer detalles internos del sistema.

### FR-016: Cerrar sesión

La persona debe poder cerrar la sesión desde el dashboard. Después del logout, el acceso a rutas protegidas debe dejar de estar disponible.

### FR-017: Eliminar datos faciales

Aunque la interfaz completa de gestión de cuenta quede fuera del MVP, el backend debe definir una operación para eliminar el perfil y su plantilla facial durante la demo o mediante una herramienta administrativa local.

## 8. Contratos de API propuestos

Los nombres son orientativos y deben confirmarse durante la spec técnica.

### POST `/api/onboarding`

Registra una persona y procesa su rostro.

**Request:** `multipart/form-data`

- `identifier`: string
- `consentAccepted`: boolean
- `image`: imagen facial puntual

**Success:** `201 Created`

```json
{
  "userId": "user_123",
  "identifier": "demo@example.com",
  "status": "enrolled"
}
```

### POST `/api/auth/face-login`

Verifica un rostro y crea una sesión.

**Request:** `multipart/form-data`

- `identifier`: string
- `image`: imagen facial puntual

**Success:** `200 OK`

```json
{
  "userId": "user_123",
  "status": "authenticated"
}
```

**Failure:** `401 Unauthorized`

La respuesta no debe distinguir innecesariamente entre identificador inexistente y rostro no coincidente.

### GET `/api/auth/me`

Devuelve el estado de la sesión actual.

### POST `/api/auth/logout`

Invalida la sesión actual.

### POST `/api/analysis/mood`

Procesa una captura para estimar el estado de ánimo. Requiere sesión.

**Request:** `multipart/form-data`

- `image`: imagen facial puntual

**Response:**

```json
{
  "label": "neutral",
  "confidence": 0.74,
  "disclaimer": "Resultado estimado por un modelo visual. No representa una medición objetiva del estado emocional."
}
```

### POST `/api/analysis/age`

Procesa una captura para estimar la edad. Requiere sesión.

**Response:**

```json
{
  "estimatedAge": 32,
  "range": {
    "min": 27,
    "max": 37
  },
  "disclaimer": "La edad es una estimación visual y puede contener un margen de error significativo."
}
```

### DELETE `/api/users/{userId}/face-data`

Elimina la plantilla facial y los datos asociados al onboarding. Requiere autorización apropiada.

## 9. Modelo de datos mínimo

### User

- `id`
- `identifier`
- `createdAt`
- `updatedAt`
- `status`

### FaceTemplate

- `id`
- `userId`
- `embedding` o referencia a almacenamiento seguro
- `modelVersion`
- `createdAt`
- `updatedAt`

### AuthSession

- `id`
- `userId`
- `createdAt`
- `expiresAt`
- `revokedAt`, opcional

### AnalysisRequest, opcional para el MVP

Si se necesita auditoría mínima, guardar únicamente:

- `id`
- `userId`
- `type`: `mood` o `age`
- `modelVersion`
- `createdAt`
- `status`

No almacenar la imagen original ni el resultado biométrico completo por defecto.

## 10. Requisitos de frontend

- Debe funcionar en escritorio y en una pantalla móvil moderna.
- Debe utilizar APIs estándar del navegador para solicitar la cámara.
- Debe mostrar claramente si la cámara está apagada, activa o bloqueada.
- Debe ofrecer una alternativa comprensible cuando el permiso sea denegado.
- Debe evitar enviar frames de video continuamente.
- Debe separar los estados de formulario, cámara, captura y procesamiento.
- Debe mostrar feedback inmediato al pulsar un botón.
- Debe conservar los resultados visibles hasta que se ejecute un nuevo análisis o se cierre la sesión.
- Debe permitir reintentar sin recargar la página cuando el error sea recuperable.
- Los botones deben ser accesibles mediante teclado y tener nombres descriptivos.
- Los resultados no deben depender exclusivamente del color para comunicar su estado.

## 11. Requisitos de backend y visión por computadora

- El backend debe validar nuevamente todos los datos recibidos desde el frontend.
- El procesamiento facial debe ejecutarse en el servidor o en un servicio controlado por la aplicación.
- El detector debe devolver como mínimo bounding box, score y cantidad de rostros detectados.
- La capa de dominio no debe importar directamente la implementación de YOLO.
- La generación de embeddings debe estar detrás de una interfaz o puerto reemplazable.
- Los modelos deben tener una versión identificable para permitir reproducibilidad de resultados.
- El umbral de verificación debe ser configurable y documentado.
- El sistema debe imponer límites de tamaño y formato de imagen.
- El sistema debe controlar timeouts y errores de carga del modelo.
- El MVP puede usar mocks deterministas para tests de dominio y contratos.

## 12. Seguridad y privacidad

Los datos faciales y las plantillas derivadas deben considerarse datos biométricos sensibles.

- Solicitar consentimiento antes del onboarding.
- Explicar de forma breve qué se procesa y con qué finalidad.
- No guardar imágenes originales salvo que sea estrictamente necesario para la demo.
- No registrar imágenes, embeddings ni respuestas biométricas en logs.
- Proteger los endpoints de análisis con sesión válida.
- Aplicar límites de frecuencia para onboarding, login y análisis.
- Usar HTTPS en cualquier entorno no local.
- Evitar mensajes de login que revelen si un identificador existe.
- Expirar las sesiones.
- Permitir eliminar la plantilla facial.
- Incluir una política clara de retención de datos.
- Usar únicamente imágenes de prueba con consentimiento.
- Documentar que el sistema no implementa liveness y puede ser vulnerable a ataques con fotografías o videos.
- No presentar edad o estado de ánimo como hechos ciertos.

## 13. Requisitos no funcionales

### Rendimiento

- La respuesta de un análisis debería mostrarse en menos de 5 segundos en el entorno local de la demo, excluyendo tiempos excepcionales de carga inicial del modelo.
- La carga de un modelo debe ocurrir una sola vez por proceso cuando sea viable.
- El frontend debe mostrar estado de procesamiento después de iniciar una operación.

### Disponibilidad y recuperación

- Un error del modelo no debe tumbar el servidor completo.
- Los errores de cámara y de análisis deben permitir reintentar.
- La aplicación debe mostrar un error controlado si el servicio de visión no está disponible.

### Observabilidad

- Registrar duración, tipo y estado de cada operación sin registrar imágenes ni embeddings.
- Incluir la versión del modelo en logs técnicos y respuestas internas cuando corresponda.
- Diferenciar errores de validación, cámara, autenticación y modelo.

### Compatibilidad

- Soporte objetivo para las últimas versiones de Chrome y Edge en escritorio.
- Soporte objetivo para navegadores móviles modernos con cámara y `getUserMedia`.
- La demo debe documentar que el acceso a cámara normalmente requiere un contexto seguro, como `localhost` o HTTPS.

## 14. Criterios de aceptación end-to-end

### AC-001: Onboarding exitoso

```text
Dado que una persona accede a onboarding
Y introduce un identificador válido
Y acepta el consentimiento
Y la captura contiene exactamente un rostro válido
Cuando confirma el registro
Entonces el sistema crea el perfil y la plantilla facial
Y muestra una confirmación de onboarding exitoso
```

### AC-002: Onboarding rechazado sin rostro

```text
Dado que la persona intenta registrarse
Cuando la captura no contiene ningún rostro
Entonces el sistema rechaza la operación
Y muestra que debe repetir la captura
Y no crea una plantilla facial
```

### AC-003: Onboarding rechazado con múltiples rostros

```text
Dado que la persona intenta registrarse
Cuando la captura contiene más de un rostro
Entonces el sistema rechaza la operación
Y solicita que aparezca una sola persona en cámara
```

### AC-004: Login exitoso

```text
Dado que existe un perfil facial registrado
Cuando la persona proporciona el identificador correcto y un rostro coincidente
Entonces el backend crea una sesión
Y el frontend redirige al dashboard
```

### AC-005: Login rechazado

```text
Dado que existe un perfil facial registrado
Cuando la captura no coincide con la plantilla registrada
Entonces el sistema no crea una sesión
Y muestra un error genérico
Y permite reintentar
```

### AC-006: Ruta protegida

```text
Dado que no existe una sesión válida
Cuando la persona intenta acceder al dashboard
Entonces es redirigida al login
```

### AC-007: Estado de ánimo

```text
Dado que la persona tiene una sesión válida
Y la cámara está disponible
Cuando pulsa "Detectar estado de ánimo"
Entonces el sistema envía una captura puntual
Y muestra un estado de carga
Y muestra una categoría o "no concluyente" al finalizar
```

### AC-008: Edad

```text
Dado que la persona tiene una sesión válida
Y la cámara está disponible
Cuando pulsa "Calcular edad"
Entonces el sistema envía una captura puntual
Y muestra una edad o rango estimado
Y muestra el disclaimer correspondiente
```

### AC-009: Logout

```text
Dado que la persona está autenticada
Cuando pulsa "Cerrar sesión"
Entonces la sesión se invalida
Y la persona sale del dashboard
Y no puede volver a acceder sin autenticarse
```

## 15. Estrategia de pruebas

### Tests unitarios

- Validación de identificadores.
- Validación de consentimiento.
- Reglas de cantidad de rostros.
- Comparación de embeddings y umbral.
- Expiración e invalidación de sesiones.
- Normalización de respuestas de edad y estado de ánimo.

### Tests de integración

- Onboarding con adaptador de detector mock.
- Login con coincidencia y no coincidencia.
- Protección de endpoints.
- Procesamiento de análisis de edad.
- Procesamiento de análisis de estado de ánimo.
- Manejo de errores del modelo.

### Tests de contrato

- Esquemas de request y response de cada endpoint.
- Códigos HTTP esperados.
- Errores de validación.
- Respuestas no reveladoras para fallos de login.

### Tests end-to-end

- Onboarding completo desde navegador.
- Login completo desde navegador.
- Acceso al dashboard.
- Ejecución de ambos análisis.
- Logout y bloqueo posterior.

Para automatizar el frontend, la cámara puede reemplazarse por un mock de `MediaDevices` y capturas de prueba controladas.

## 16. Métricas de éxito de la demo

- Una persona puede completar onboarding en menos de 2 minutos.
- Una persona registrada puede completar login en menos de 30 segundos, sin contar problemas de permisos.
- El flujo completo puede ejecutarse sin intervención manual del equipo técnico.
- El 100% de las rutas protegidas rechaza solicitudes sin sesión.
- Los errores principales de cámara, captura, autenticación y modelo se muestran de forma entendible.
- Los tests de aceptación cubren los tres flujos principales: onboarding, login y análisis.
- Ninguna imagen facial o plantilla aparece en logs de aplicación.

Estas métricas evalúan la calidad de la demo, no la exactitud biométrica o psicológica de los modelos.

## 17. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| YOLO detecta incorrectamente el rostro | Alto | Validar score, tamaño y cantidad de rostros; permitir repetir captura |
| El login acepta o rechaza incorrectamente | Alto | Usar verificación 1:1, calibrar umbral y documentar limitaciones |
| Una foto suplanta a la persona | Alto | Declarar ausencia de liveness; dejar liveness como fase futura |
| Edad estimada con error significativo | Medio | Mostrar rango o disclaimer y no usar el dato para decisiones |
| Estado de ánimo no representa el estado real | Alto | Usar lenguaje de estimación, incluir `no concluyente` y limitar el uso |
| Permiso de cámara denegado | Medio | Mostrar instrucciones y permitir reintentar |
| Modelo lento o pesado | Medio | Cargar modelos una vez, usar mocks para desarrollo y medir latencia |
| Exposición de datos biométricos | Alto | No guardar imágenes, no loguear embeddings, proteger almacenamiento y borrar datos |
| Resultados inconsistentes entre máquinas | Medio | Fijar versiones de modelos, dependencias y fixtures de prueba |
| Cambios de iluminación o cámara | Medio | Guías de captura, validación de calidad y mensajes de reintento |

## 18. Fases de implementación

### Fase 1: Skeleton y contrato

- Crear navegación y vistas.
- Definir modelos de dominio.
- Definir contratos HTTP.
- Crear adaptadores mock para detección, embedding, edad y estado de ánimo.
- Implementar tests de contrato y dominio.

### Fase 2: Onboarding

- Implementar formulario.
- Integrar cámara.
- Implementar captura puntual.
- Crear perfil y plantilla mock.
- Cubrir validaciones y errores.

### Fase 3: Login y sesión

- Implementar verificación 1:1.
- Configurar umbral.
- Crear e invalidar sesiones.
- Proteger dashboard.
- Añadir logout.

### Fase 4: Dashboard y análisis

- Mostrar cámara autenticada.
- Implementar botón de estado de ánimo.
- Implementar botón de edad.
- Mostrar estados de carga, resultados y errores.

### Fase 5: Modelos reales

- Sustituir detector mock por YOLO.
- Integrar modelo de embeddings.
- Integrar modelo de edad.
- Integrar modelo de estado de ánimo.
- Medir tiempos y ajustar thresholds.

### Fase 6: Hardening de demo

- Revisar privacidad y logs.
- Implementar borrado de datos faciales.
- Añadir rate limiting básico.
- Ejecutar pruebas end-to-end.
- Documentar instalación, modelos, limitaciones y flujo de presentación.

## 19. Decisiones técnicas pendientes

- Framework de frontend.
- Framework de backend.
- Base de datos o almacenamiento local para la demo.
- Modelo específico de embeddings faciales.
- Modelo específico para edad.
- Modelo específico para estado de ánimo.
- Formato y tamaño máximo de imágenes.
- Algoritmo de similitud y estrategia de calibración del umbral.
- Duración y mecanismo de la sesión.
- Si los resultados de análisis se almacenarán o serán únicamente transitorios.
- Si el modo demo permitirá usar mocks mediante configuración.

## 20. Criterio de finalización del MVP

El MVP se considera terminado cuando una persona puede:

1. Abrir la aplicación.
2. Completar el onboarding con consentimiento.
3. Capturar y registrar su rostro.
4. Cerrar o abandonar la pantalla.
5. Volver a iniciar sesión con el rostro registrado.
6. Acceder al dashboard protegido.
7. Ver su cámara.
8. Ejecutar el análisis de estado de ánimo.
9. Ejecutar la estimación de edad.
10. Ver resultados y disclaimers.
11. Cerrar sesión.

Además, los tests principales deben pasar y la documentación debe dejar claro qué parte utiliza modelos reales, qué parte utiliza mocks y cuáles son las limitaciones del sistema.
