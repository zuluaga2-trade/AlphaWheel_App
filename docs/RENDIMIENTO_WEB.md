# Recomendaciones para mejorar el rendimiento de AlphaWheel en la versión web

La app en Streamlit Cloud (y en general en navegador) puede ir lenta sobre todo tras las últimas actualizaciones (gauges de análisis del riesgo, columnas nuevas, más cálculos). Aquí tienes causas probables y acciones concretas.

---

## 1. Causas principales de lentitud

- **Re-ejecución completa del script**: En Streamlit, cada interacción (clic, cambio de selector, etc.) vuelve a ejecutar todo el script. Con un cockpit de más de 2000 líneas, eso implica muchas consultas a BD, llamadas a APIs y construcción de gráficos en cada “refresh”.
- **Consultas a BD sin caché**: `get_accounts_by_user`, `get_trades_by_account`, `get_position_summary` se llaman en cada rerun sin `@st.cache_data`, por lo que cada vez se vuelve a hablar con PostgreSQL/SQLite.
- **Cotizaciones Tradier en el dashboard**: En la pestaña Cuentas, el valor “a precios actuales” necesita el precio de cada ticker. Antes se usaba `provider.get_quote(t)` en bucle **sin** la función cacheada; cada rerun hacía N peticiones HTTP (una por ticker). **Corregido**: ahora se usa `get_tradier_quote_cached` (TTL 30 min y opcionalmente caché compartida entre usuarios).
- **Gráficos Plotly (gauges)**: Los medidores de “Análisis del riesgo” (`build_gauge_price_axis`) se construyen en cada rerun sin caché. Crear figuras Plotly es costoso en CPU y en serialización al enviarlas al navegador.
- **CSS y estilos**: Tanto `main_app.py` como `cockpit` inyectan mucho CSS en cada ejecución; no es lo más grave, pero suma trabajo en cada rerun.

---

## 2. Cambios ya aplicados

- **Cotizaciones en el dashboard (Cuentas)**: El bucle que obtiene precios de mercado para “Valor actual vs invertido” y la tabla de posiciones ahora usa **`get_tradier_quote_cached`** (TTL 30 min). Los mismos tickers no disparan nuevas peticiones a Tradier en cada rerun.
- **Caché Tradier compartida**: TTL 30 min para quote, expirations y chain. Secrets o **variables de entorno** (se usa la que esté definida): **`ALPHAWHEEL_TRADIER_QUOTE_TOKEN`** o **`TRADIER_QUOTE_TOKEN`**. La app usa caché compartida por ticker: si un usuario ya consultó un ticker, cualquier otro reutiliza el resultado.
- **Caché Alpha Vantage compartida**: Earnings 48 h, overview 24 h. Secrets o **variables de entorno**: **`ALPHAWHEEL_AV_KEY`** o **`AV_KEY`**. Earnings y overview por ticker se comparten entre todos los usuarios.

---

## 3. Recomendaciones adicionales (por prioridad)

### 3.1 Cachear lecturas de base de datos (alto impacto)

En `app/cockpit.py` (y si usas `main_app.py`, también ahí), define funciones envueltas con `@st.cache_data(ttl=60)` (o 30–120 s según lo “fresco” que quieras el dato) para:

- Lista de cuentas del usuario: por ejemplo una función `get_accounts_by_user_cached(user_id)` que llame a `get_accounts_by_user` y esté cacheada.
- Trades abiertos y resumen de posición: por ejemplo `get_trades_by_account(account_id, status="OPEN")` y `get_position_summary(account_id)` cacheados por `account_id`.

**Importante**: Si el usuario abre/cierra posiciones o cambia datos, el TTL hace que en 30–60 s se vea el cambio. Para acciones inmediatas (ej. “Acabo de registrar un trade”), puedes invalidar caché con `st.cache_data.clear()` justo después de ese registro, o usar un TTL corto (30 s).

### 3.2 Cachear la construcción de gauges (impacto medio-alto)

En `app/position_chart_utils.py`, la función `build_gauge_price_axis` (y si se usan, las otras que generan figuras) puede cachearse por sus argumentos:

- Añadir una función wrapper que reciba los parámetros que definen el gauge (strike, be, precio, dte, status_label, etc.) y devuelva la figura.
- Usar `@st.cache_data(ttl=60)` en esa wrapper. Mientras los inputs no cambien, Streamlit reutilizará la misma figura en lugar de recalcularla.

Así reduces trabajo de CPU y de serialización en cada rerun, sobre todo en pantallas con varios gauges (screener, detalle de posición, dashboard).

### 3.3 Reducir reruns con `st.fragment` (Streamlit 1.33+)

Si tu versión de Streamlit es ≥ 1.33, puedes usar `@st.fragment` en bloques que no necesiten re-ejecutar toda la página al interactuar (por ejemplo, un botón “Actualizar solo esta sección”). Así, al pulsar ese botón solo se vuelve a ejecutar el fragmento y no todo el script, lo que aligera mucho la sensación de lentitud en web.

### 3.4 Evitar consultas repetidas en el mismo rerun

Revisa que, en un mismo rerun, no llames varias veces a `get_trades_by_account(account_id, status="OPEN")` o `get_position_summary(account_id)` para el mismo `account_id`. Si es así, guarda el resultado en una variable y reutilízala (o centraliza en una función cacheada como en 3.1).

### 3.5 Configuración de Streamlit en `.streamlit/config.toml`

Puedes añadir o ajustar:

```toml
[server]
# Reducir frecuencia de heartbeat si la conexión es estable (menos tráfico)
maxUploadSize = 200
enableCORS = false

[browser]
gatherUsageStats = false
```

Y, si usas Streamlit Cloud, en **Advanced settings** revisa que no haya un límite de memoria muy bajo; los gauges y varias pestañas con datos pueden consumir bastante.

### 3.6 Cargar datos pesados solo cuando haga falta

En la pestaña **Reportes** (bitácora, PDF, Excel), los datos se cargan al entrar en esa pestaña. Mantén ese patrón: no cargar historial completo ni cadenas de opciones en el primer rerun si no es necesario. El screener ya usa caché para Tradier y Alpha Vantage; asegúrate de no duplicar llamadas fuera de esas funciones cacheadas.

---

## 4. Resumen rápido

| Acción                               | Impacto   | Dificultad |
|--------------------------------------|-----------|------------|
| Cotizaciones Tradier cacheadas (30 min + compartida) | Alto      | Hecho      |
| Cachear `get_accounts_by_user`, trades, position_summary | Alto      | Baja       |
| Cachear construcción de gauges       | Medio-alto| Media      |
| Usar `st.fragment` en bloques locales| Alto      | Media      |
| Unificar y reutilizar consultas en el mismo rerun | Medio     | Baja       |
| Ajustar `config.toml` / recursos Cloud | Bajo-medio | Baja     |

Con el cambio ya aplicado (cotizaciones cacheadas en el dashboard) deberías notar menos lentitud al abrir la pestaña Cuentas y al cambiar de cuenta. Aplicando además el caché de BD y de gauges, la versión web debería acercarse al rendimiento que tenías antes de las últimas actualizaciones.
