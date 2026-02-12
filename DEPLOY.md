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
