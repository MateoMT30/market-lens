# Market Lens en la nube (gratis, sin tu PC)

Esto hace que tu app funcione **sola, todos los días, sin encender el computador**:

- **GitHub Actions** corre el motor cada día, calcula la cartera del mes y te avisa por **Telegram** si cambia.
- **GitHub Pages** publica tu tablero en una **URL fija y permanente** que puedes abrir desde cualquier lugar (celular incluido).
- Costo: **$0**.

---

## Pasos (una sola vez, ~15 minutos)

### 1. Crear cuenta de GitHub
Entra a https://github.com y crea una cuenta gratis (si ya tienes, salta este paso).

### 2. Crear el repositorio
- Arriba a la derecha: **+ → New repository**.
- Nombre: por ejemplo `market-lens`.
- Déjalo **Public** (necesario para que GitHub Pages sea gratis).
- Marca **Add a README** NO (ya traemos uno). Clic en **Create repository**.

### 3. Subir estos archivos
En la página del repo vacío: **uploading an existing file**. Arrastra TODO lo que hay dentro de esta carpeta `deploy/`:
```
motor_ensemble.py
README.md
.gitignore
docs/         (con index.html adentro)
.github/      (con workflows/actualizar.yml adentro)
```
> Si al arrastrar no aparecen las carpetas `.github` o `docs`, súbelas por separado con **Add file → Upload files** y escribe la ruta a mano (ej. `.github/workflows/actualizar.yml`).
Clic en **Commit changes**.

### 4. Guardar tu token de Telegram como SECRETO (¡importante!)
El token NO va en el código. Va aquí, cifrado:
- En el repo: **Settings → Secrets and variables → Actions → New repository secret**.
- Crea dos secretos:
  - Nombre: `TELEGRAM_TOKEN`  ·  Valor: *(tu token de @BotFather)*
  - Nombre: `TELEGRAM_CHAT_ID`  ·  Valor: *(tu chat id)*

### 5. Prender la automatización
- Pestaña **Actions** → si pide confirmar, dale **I understand my workflows, enable them**.
- Entra a "Actualizar cartera Market Lens" → **Run workflow** para probarlo ya (sin esperar al día siguiente).
- Debe terminar en verde y te debe llegar la cartera a Telegram.

### 6. Prender el tablero web (GitHub Pages)
- **Settings → Pages**.
- En "Build and deployment", Source: **Deploy from a branch**.
- Branch: **main**, carpeta: **/docs**. **Save**.
- Espera 1–2 minutos. Tu tablero quedará en:
  `https://TU-USUARIO.github.io/market-lens/`
  (Guarda ese enlace: es fijo y funciona desde cualquier lado.)

---

## Listo
- Cada día a las 7:00 AM (hora Colombia) el motor corre solo en la nube.
- Si la cartera cambia, te llega la alerta a Telegram.
- El tablero web siempre muestra la última cartera.
- **Tu PC puede estar apagado.**

## Notas honestas
- Los datos vienen de Yahoo Finance. En raras ocasiones Yahoo puede bloquear a servidores en la nube; si ves que un día falla en la pestaña **Actions**, avísame y cambiamos la fuente de datos o pasamos a un servidor propio.
- El token quedó fuera del código y solo tú lo ves en Secrets. Si alguna vez se te expuso antes, créalo de nuevo con @BotFather y actualiza el secreto.
- Esto es una herramienta con respaldo histórico, no una recomendación financiera personalizada.
