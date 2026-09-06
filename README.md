# Backend de VitaFlow

API local para analizar fotografías de comida. Reprocesa cada imagen a JPEG —sin EXIF— y
puede usar un resultado demostrativo o visión real. El modo recomendado intenta
GLM-4.6V-Flash y utiliza GPT-5.6 Luna como respaldo automático ante fallos técnicos.

Cada ingrediente incluye gramos, calorías, proteínas, carbohidratos y grasas correspondientes a
esa porción. La app usa esa base para recalcular el plato al corregir cantidades, sin realizar una
segunda llamada al modelo. Los totales del servidor se normalizan con la suma de ingredientes.

## Arranque rápido sin API key

```bash
cd vitaflow_backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Comprueba el servidor en `http://127.0.0.1:8000/health`. La documentación interactiva
queda disponible en `http://127.0.0.1:8000/docs`.

## Activar visión real híbrida

Necesitas una clave de Z.AI y una de OpenAI. Configúralas en la terminal antes de iniciar Uvicorn:

```bash
export VITAFLOW_AI_MODE=hybrid
export ZAI_API_KEY="tu-clave-zai"
export ZAI_MODEL=glm-4.6v-flash
export OPENAI_API_KEY="tu-clave-openai"
export OPENAI_MODEL=gpt-5.6-luna
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

El fallback se ejecuta únicamente si GLM produce un timeout, error HTTP o respuesta que no
cumple el contrato nutricional. Una confianza baja no dispara una segunda llamada: se muestra
para revisión humana. También existen los modos `zai` y `openai` para probar cada proveedor
por separado.

No guardes las claves en `local.properties`, el APK ni Git. `store: false` evita solicitar
almacenamiento del response en la API y el backend no escribe la fotografía en disco.

También puedes copiar `.env.example` a `.env`, completar sus valores y arrancar con
`uvicorn app.main:app --env-file .env --reload --host 127.0.0.1 --port 8000`. El archivo
`.env` está excluido de Git.

## Protección y códigos de barras

`GET /v1/products/{codigo}` consulta Open Food Facts y devuelve los nutrientes por porción
cuando están disponibles. No utiliza IA y siempre presenta el resultado como editable.

Todas las rutas `/v1/` tienen un límite configurable con
`VITAFLOW_RATE_LIMIT_PER_MINUTE=30`. Para una beta cerrada también puedes definir un valor
aleatorio largo en `VITAFLOW_CLIENT_TOKEN`; la app debe compilarse con el mismo valor en
`local.properties`. No uses ese mecanismo como cuenta de usuario en producción: el token de
una app instalada puede extraerse.

## Preparar un despliegue HTTPS

El directorio incluye un `Dockerfile` sin claves. Comprueba la imagen localmente con:

```bash
docker build -t vitaflow-api .
docker run --env-file .env -p 8000:8000 vitaflow-api
```

Puedes subir esa imagen a un servicio administrado que termine TLS y entregue un dominio
HTTPS. Configura las claves exclusivamente como secretos del proveedor y cambia
`VITAFLOW_API_BASE_URL` por ese dominio antes de generar el APK de distribución.

Antes de una publicación abierta todavía hacen falta autenticación real por usuario,
rate limiting distribuido (por ejemplo Redis), métricas sin contenido sensible y una política
de retención explícita.

## Pruebas

```bash
cd vitaflow_backend
source .venv/bin/activate
python -m unittest discover -s tests
```
