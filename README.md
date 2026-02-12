# AlphaWheel Pro

Aplicación web **multi-usuario** para el control de estrategias de opciones (La Rueda: CSP, CC, roll-over, compra directa, dividendos y ajustes). Cada usuario puede gestionar **varias cuentas** con aislamiento total de datos. Diseño profesional, listo para desplegar o publicar en GitHub.

## Características

- **Autenticación**: registro e inicio de sesión por email y contraseña. Sesión por usuario. El último email se recuerda en este dispositivo (solo hay que volver a escribir la contraseña tras cerrar sesión o actualizar).
- **Multi-usuario y multi-cuenta**: cada usuario ve solo sus cuentas; puede crear varias (ej. IRA, Taxable, Sandbox).
- **Token Tradier**: configurable por cuenta en **Mi cuenta**. Precios en tiempo real y estado Online/Offline.
- **Dashboard**: Capital, meta anual, máximo por ticker, utilización, KPIs (ON TRACK / BEHIND), donut por ticker, barras de objetivo anual y expiraciones.
- **Posiciones abiertas**: tabla con Activo, Estrategia, Contratos, Fechas, Precio MKT, Strike, Prima, Breakeven, Diagnóstico (OK/Riesgo), Retorno, Anualizado, POP.
- **Radiografía P&L**: gráfico Precio vs Ganancia/Pérdida por posición; Strike, BE y Precio actual; métricas (P&L actual, max ganancia/pérdida).
- **Gestión de posición**: editar Strike, Prima, Expiración, Comentario; borrar trade o cerrar posición.
- **Roll-over**: cerrar CSP/CC y abrir nueva pierna desde el sidebar.
- **Add Position**: registrar CSP, CC, Compra directa, Dividendo, Ajuste.
- **Reportes**: bitácora por rango de fechas; Tax Efficiency; exportación CSV, Excel, PDF.
- **Cifras**: todas con 2 decimales.

## Requisitos

- Python 3.10+
- Dependencias en `requirements.txt`

## Instalación

```bash
git clone <tu-repo>
cd AlphaWheel_App
pip install -r requirements.txt
```

## Ejecución

**Aplicación con login (recomendada):**

```bash
streamlit run app/Home.py
```

Se abrirá la pantalla de **Iniciar sesión** / **Registrarse**. Tras registrarte o iniciar sesión, accedes al cockpit (Dashboard, Reportes, Mi cuenta). Cada usuario gestiona sus propias cuentas.

**App clásica (sin login, selector de usuario):**

```bash
streamlit run main_app.py
```

## Estructura del proyecto

```
AlphaWheel_App/
├── app/
│   ├── Home.py          # Entrada: login/registro → cockpit
│   ├── cockpit.py       # Dashboard, Reportes, Mi cuenta
│   ├── session_helpers.py
│   └── styles.py        # CSS profesional
├── auth/
│   └── auth.py         # Login, registro, hash de contraseña
├── business/
│   └── wheel.py        # Lógica La Rueda (CSP, CC, asignación, etc.)
├── database/
│   ├── db.py           # Acceso BD (User, Account, Trade, etc.)
│   └── schema.sql      # Esquema multi-usuario
├── engine/
│   └── calculations.py # DTE, breakeven, RoC, anualizado, etc.
├── providers/
│   ├── base.py         # Interfaz proveedor
│   └── tradier.py      # Tradier API
├── reports/
│   └── bitacora.py     # CSV, Excel, PDF, Tax Efficiency
├── config.py
├── requirements.txt
├── main_app.py         # Versión sin login (selector usuario)
└── README.md
```

## Seguridad y GitHub

- **Nunca** subas tu Access Token de Tradier al repositorio. Configura el token solo dentro de la app (Mi cuenta).
- La base de datos `trading_app.db` está en `.gitignore`; no se sube a GitHub.
- Las contraseñas se almacenan hasheadas (salt + SHA-256). Para entornos críticos valora bcrypt/passlib.

## Despliegue en Streamlit Cloud (GitHub) — pocos usuarios autorizados

**Instrucciones paso a paso**: ver **[DEPLOY.md](DEPLOY.md)** (crear repo en GitHub, subir código, desplegar en Streamlit Cloud y configurar la lista de emails autorizados).

Para compartir la app con **pocos usuarios** manteniendo **acceso solo por email autorizado**:

1. **Publica el repo en GitHub** (público o privado; Streamlit Cloud puede conectar ambos).

2. **Despliega en [Streamlit Community Cloud](https://share.streamlit.io)**:
   - Conecta tu cuenta de GitHub.
   - New app → selecciona el repo, rama y archivo de entrada: `app/Home.py`.
   - En **Advanced settings** → **Secrets**, añade las variables de entorno.

3. **Restricción por email** (solo usuarios autorizados):
   - En la app en Streamlit Cloud → **Settings** → **Secrets**, pega (en formato TOML):
   ```toml
   ALPHAWHEEL_ALLOWED_EMAILS = "user1@email.com,user2@email.com,user3@email.com"
   ```
   - Streamlit expone las claves de Secrets como variables de entorno; la app las usa para permitir solo esos emails.
   - Solo esos emails podrán **registrarse** e **iniciar sesión**. Cualquier otro verá "Acceso no autorizado" al registrarse o no podrá entrar al iniciar sesión.

4. **Credenciales y datos de cada usuario**:
   - Los tokens (Tradier) y claves (Alpha Vantage) se guardan **por usuario/cuenta** en la base de datos, no en el código.
   - La BD no es accesible desde fuera; solo la app en el servidor la lee. Cada usuario ve solo sus cuentas y posiciones.

5. **Persistencia: no perder usuarios ni datos en redeploys**:
   - **Local**: la BD está en la raíz del proyecto (`trading_app.db`) y persiste entre reinicios y actualizaciones; no hace falta volver a registrarse.
   - **Streamlit Cloud (y otros hosts)**: el disco es efímero; si no configuras BD externa, cada redeploy borra usuarios y datos. Para evitarlo, usa **PostgreSQL** y define en **Secrets** la URL de conexión:
   ```toml
   ALPHAWHEEL_DATABASE_URL = "postgresql://usuario:contraseña@host:5432/nombre_bd"
   ```
   - **Obtener PostgreSQL gratis**: [Neon](https://neon.tech) o [Supabase](https://supabase.com) ofrecen PostgreSQL en la nube (plan free). Creas un proyecto, copias la connection string y la pegas en `ALPHAWHEEL_DATABASE_URL`. La app crea las tablas solas al arrancar; usuarios y posiciones quedan guardados entre redeploys.

6. **Resumen**: acceso restringido por lista de emails + credenciales y cuentas en la app. Con `ALPHAWHEEL_DATABASE_URL` (PostgreSQL) no se pierden usuarios ni datos al actualizar el código.

## Licencia

Uso bajo tu propia responsabilidad. No constituye asesoramiento financiero.
