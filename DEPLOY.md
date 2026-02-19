# AlphaWheel Pro — Subir a GitHub y desplegar en Streamlit Cloud

Guía paso a paso para publicar el proyecto en tu cuenta de GitHub y poner la app en línea con acceso restringido por email.

---

## 1. Subir el proyecto a GitHub

### 1.1 Crear el repositorio en GitHub

1. Entra en [github.com](https://github.com) e inicia sesión (cuenta donde quieras el repo).
2. Clic en **"+"** (arriba derecha) → **"New repository"**.
3. Rellena:
   - **Repository name**: por ejemplo `AlphaWheel_App` (o el nombre que prefieras).
   - **Description** (opcional): "App multi-usuario para estrategias de opciones (CSP, CC, La Rueda)".
   - **Public** o **Private**: tú eliges. Con **Private** solo quien tenga acceso al repo verá el código; Streamlit Cloud puede desplegar repos privados si conectas tu cuenta.
   - **No** marques "Add a README", "Add .gitignore" ni "Choose a license" si ya tienes el proyecto en tu PC (evitas conflictos).
4. Clic en **"Create repository"**.
5. En la página del repo nuevo, copia la **URL** del repositorio (ej. `https://github.com/TU_USUARIO/AlphaWheel_App.git`).

### 1.2 Inicializar Git en tu PC (si aún no está)

Abre una terminal en la carpeta del proyecto (donde está `app/`, `config.py`, `README.md`, etc.):

```bash
cd C:\Users\zulua\OneDrive\Desktop\AlphaWheel_App
```

Si nunca has usado Git en este proyecto:

```bash
git init
git add .
git status
```

Revisa que **no** se incluyan archivos sensibles (`.db`, `.env`, `venv/`, `.streamlit/secrets.toml` están en `.gitignore`). Si algo que no debe subirse aparece en la lista, añádelo a `.gitignore` y vuelve a `git add .`.

### 1.3 Primer commit y enlace con GitHub

```bash
git commit -m "AlphaWheel Pro: app multi-usuario, restricción por email, listo para despliegue"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/AlphaWheel_App.git
git push -u origin main
```

Sustituye `TU_USUARIO` por tu usuario de GitHub y `AlphaWheel_App` por el nombre del repo si lo cambiaste.

Si GitHub te pide autenticación, usa tu usuario y un **Personal Access Token** (Settings → Developer settings → Personal access tokens) como contraseña, o configura SSH si ya lo tienes.

---

## 2. Desplegar en Streamlit Cloud

### 2.1 Conectar GitHub con Streamlit

1. Entra en [share.streamlit.io](https://share.streamlit.io).
2. Inicia sesión con **GitHub** (autoriza a Streamlit a leer tus repos).
3. Clic en **"New app"**.

### 2.2 Configurar la app

- **Repository**: elige `TU_USUARIO/AlphaWheel_App` (o el nombre que pusiste).
- **Branch**: `main`.
- **Main file path**: `app/Home.py` (punto de entrada con login/registro).

### 2.2.1 Web y móvil igual que la versión local

Para que la app en **web** y **móvil** se vea y se comporte igual que en local:

1. **Configuración unificada**: El repositorio incluye `.streamlit/config.toml` con tema oscuro, colores y barra lateral coherentes. Streamlit Cloud usa este archivo al desplegar, así que web y móvil heredan la misma apariencia que en tu PC.
2. **Mismo punto de entrada**: Si en local usas `streamlit run main_app.py`, la interfaz (formularios en sidebar, Screener, Mi Cuenta) es la de **cockpit** cuando despliegas con `app/Home.py`: tras el login se carga el mismo cockpit con los mismos formularios en la barra lateral.
3. **Barra lateral abierta**: Tanto `app/Home.py` como `main_app.py` usan `initial_sidebar_state="expanded"`, así que la barra lateral aparece abierta por defecto en local, web y móvil.
4. **Tras subir cambios**: Después de un `git push`, haz un **Reboot** de la app en Streamlit Cloud (ver 2.5) para que se aplique el último código y la config.

En **móvil**, si la barra lateral se colapsa por espacio, el usuario puede abrirla con el icono **>** arriba a la izquierda; los formularios (Screener, Cuenta activa, etc.) están dentro de esa barra.

### 2.3 Restricción por email (usuarios autorizados)

Antes de desplegar, abre **"Advanced settings"** y en **Secrets** pega exactamente esto (formato TOML):

```toml
ALPHAWHEEL_ALLOWED_EMAILS = "zuluaga2@gmail.com,deiviselchutas@gmail.com,zuluagacamilo1@hotmail.com"
```

- **zuluaga2@gmail.com**: administrador (tu cuenta).
- **deiviselchutas@gmail.com**, **zuluagacamilo1@hotmail.com**: usuarios autorizados.

Solo estos tres emails podrán **registrarse** e **iniciar sesión**. Cualquier otro verá "Acceso no autorizado" al registrarse o no podrá entrar.

Guarda y haz clic en **"Deploy!"**.

### 2.4 Tras el despliegue

- La app tendrá una URL tipo: `https://TU_APP.streamlit.app`.
- Puedes compartir ese enlace solo con los tres usuarios; ellos se registran con su email (y contraseña) y ya pueden usar la app.
- Para cambiar la lista de emails más adelante: en [share.streamlit.io](https://share.streamlit.io) → tu app → **Settings** → **Secrets** → edita `ALPHAWHEEL_ALLOWED_EMAILS` y guarda (la app se redesplegará).

### 2.5 Redeploy manual (cuando los cambios no se ven en la app)

Si hiciste `git push` pero la app en `alphawheel.streamlit.app` sigue mostrando la versión antigua, fuerza un **reboot** para que Streamlit Cloud reconstruya con el último código:

**Opción A — Desde la propia app**

1. Abre tu app: **https://alphawheel.streamlit.app**
2. En la esquina **inferior derecha** haz clic en **"Manage app"** (o el botón con la flecha).
3. Se abre el panel de gestión. Haz clic en el menú de **tres puntos** (⋮) y elige **"Reboot app"**.
4. Confirma con **"Reboot"**. La app mostrará "Your app is in the oven" unos minutos y volverá con el código actualizado.

**Opción B — Desde el workspace de Streamlit**

1. Entra en **[share.streamlit.io](https://share.streamlit.io)** e inicia sesión.
2. En la lista de apps, localiza **AlphaWheel Pro** (o el nombre de tu app).
3. Haz clic en el **menú de tres puntos** (⋮) al lado de la app y elige **"Reboot"**.
4. Confirma con **"Reboot"**.

**Si sigue sin actualizarse:** en [share.streamlit.io](https://share.streamlit.io) → tu app → **Settings** → comprueba que **Branch** sea `main` y **Main file path** sea `app/Home.py`. Revisa también que el último commit esté en GitHub (repo `zuluaga2-trade/AlphaWheel_App`).

### 2.6 Error "UndefinedTable" o "tabla User no existe" (PostgreSQL)

Si al hacer login ves `psycopg2.errors.UndefinedTable` (tabla `User` no existe), la app está usando **PostgreSQL** pero las tablas aún no se han creado. Para que funcionen login y datos en la nube:

1. **Configura la base PostgreSQL en Secrets** (Neon, Supabase u otro): en [share.streamlit.io](https://share.streamlit.io) → tu app → **Settings** → **Secrets**, añade la URL de PostgreSQL (ver sección 5 más abajo):
   ```toml
   ALPHAWHEEL_DATABASE_URL = "postgresql://usuario:contraseña@host:5432/nombre_bd?sslmode=require"
   ```
2. **Reinicia la app** (Reboot, ver 2.5). Al arrancar, la app ejecuta el esquema `schema_pg.sql` y crea las tablas (`User`, `Account`, `Trade`, etc.) automáticamente.
3. Si tras el reboot sigue el error, revisa en **Manage app** → **Logs** el mensaje exacto (por ejemplo "Esquema PostgreSQL no encontrado" o errores de permisos en la BD).

---

## 3. Probar en local con la misma restricción (opcional)

Si quieres probar la restricción por email en tu PC antes de subir:

1. Copia `.streamlit/secrets.toml.example` como `.streamlit/secrets.toml`.
2. Edita `.streamlit/secrets.toml` y pega la lista de emails:

```toml
ALPHAWHEEL_ALLOWED_EMAILS = "zuluaga2@gmail.com,deiviselchutas@gmail.com,zuluagacamilo1@hotmail.com"
```

3. Ejecuta la app como siempre: `streamlit run app/Home.py`. Streamlit carga `secrets.toml` y expone las claves como variables de entorno; la app aplicará la restricción.

**Importante**: `.streamlit/secrets.toml` está en `.gitignore`; no se sube a GitHub. Los emails solo los pones tú en Secrets (Streamlit Cloud) o en tu PC.

---

## 4. Resumen

| Paso | Dónde | Qué hacer |
|------|--------|-----------|
| 1 | GitHub | Crear repo → copiar URL |
| 2 | PC | `git init` (si aplica) → `git add .` → `git commit` → `git remote add origin URL` → `git push -u origin main` |
| 3 | Streamlit Cloud | New app → repo `app/Home.py` → Advanced settings → Secrets: `ALPHAWHEEL_ALLOWED_EMAILS = "..."` → Deploy |
| 4 | Uso | Compartir la URL de la app solo con los usuarios autorizados; ellos se registran con su email y contraseña |
| 5 (opcional) | Neon/Supabase + Secrets | Añadir `ALPHAWHEEL_DATABASE_URL` con URL de PostgreSQL para que usuarios y datos no se pierdan en redeploys (sección 5) |

Credenciales (Tradier, Alpha Vantage) y datos de cada usuario se guardan en la base de datos de la app; cada uno solo ve sus cuentas.

---

## 5. No perder usuarios ni datos en redeploys (PostgreSQL)

En Streamlit Cloud el disco es efímero: cada redeploy borra la base de datos y hay que volver a registrarse. Para evitarlo, usa **PostgreSQL** en la nube y define la URL en Secrets.

### 5.1 Crear PostgreSQL gratis (Neon o Supabase)

**Opción A — [Neon](https://neon.tech)**  
1. Regístrate (gratis).  
2. Crea un proyecto y una base de datos.  
3. En **Connection string** copia la URL tipo:  
   `postgresql://usuario:contraseña@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`

**Opción B — [Supabase](https://supabase.com)**  
1. Regístrate (gratis).  
2. Crea un proyecto.  
3. En **Settings → Database** copia la **Connection string** (URI). Suele ser:  
   `postgresql://postgres.[ref]:[PASSWORD]@aws-0-region.pooler.supabase.com:6543/postgres`

### 5.2 Añadir la URL a Streamlit Secrets

En [share.streamlit.io](https://share.streamlit.io) → tu app → **Settings** → **Secrets**, añade (o edita) y deja todo en un solo bloque TOML:

```toml
ALPHAWHEEL_ALLOWED_EMAILS = "zuluaga2@gmail.com,deiviselchutas@gmail.com,zuluagacamilo1@hotmail.com"
ALPHAWHEEL_DATABASE_URL = "postgresql://usuario:contraseña@host:5432/nombre_bd"
```

Sustituye `ALPHAWHEEL_DATABASE_URL` por la URL real que te dio Neon o Supabase (con usuario, contraseña, host y nombre de BD).  
La app crea las tablas al arrancar; no hace falta configurar nada más. Tras eso, usuarios y posiciones **persisten** entre redeploys y actualizaciones de código.

### 5.3 Misma base de datos en local y en la nube

Para que **local (tu PC) y la versión web** usen los **mismos datos** (mismos usuarios, cuentas, trades, reportes):

1. **En la nube**: ya tienes `ALPHAWHEEL_DATABASE_URL` en **Secrets** de Streamlit Cloud con la URL de Neon (o Supabase).
2. **En local**: usa la **misma URL** de una de estas formas:
   - **Opción A** — Crea o edita `.streamlit/secrets.toml` (no se sube a GitHub) y añade:
     ```toml
     ALPHAWHEEL_DATABASE_URL = "postgresql://usuario:contraseña@host/neondb?sslmode=require"
     ```
   - **Opción B** — Antes de ejecutar la app, define la variable de entorno en PowerShell:
     ```powershell
     $env:ALPHAWHEEL_DATABASE_URL="postgresql://usuario:contraseña@host/neondb?sslmode=require"
     py -m streamlit run app/Home.py
     ```

Con la misma URL en ambos sitios, la app usa siempre la base PostgreSQL en la nube: los datos son **idénticos** en local y en el navegador.
