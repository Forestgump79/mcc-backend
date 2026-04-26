# MCC Backend

Backend en FastAPI para:

- analizar contexto de mercado cripto en tiempo real,
- generar una sugerencia de entrada simple,
- ejecutar un backtest básico (SMA crossover) sobre datos de Binance,
- exponer un frontend demo para visualizar resultados.

## Estructura actual

- `main.py`
  - `GET /` (frontend demo)
  - `GET /mcc/market-context`
  - `GET /mcc/signals`
  - `POST /mcc/backtest`
  - `GET /health`
- `frontend/index.html`
- `tests/test_core.py`
- `requirements.txt`

---

## Si los comandos no te funcionan (muy importante)

## ¿Dónde está alojada la app y cómo la "activa" Python?

Esta app **no está alojada en internet automáticamente**.

- El código vive en tu carpeta local del proyecto (por ejemplo `mcc-backend`).
- Cuando ejecutas `python -m uvicorn main:app ...`, Python **arranca un servidor web local** en tu máquina.
- Ese servidor queda escuchando en `http://localhost:8000`.
- "localhost" significa: *tu propia computadora*.

En otras palabras: Python no "activa" algo remoto; simplemente ejecuta el archivo `main.py` como servicio web local.

### Flujo correcto (resumen rápido)

1. Abres una terminal en la carpeta del proyecto `mcc-backend`.
2. Creas y activas el entorno virtual.
3. Instalas dependencias.
4. Levantas el servidor con `python -m uvicorn ...`.
5. Abres `http://localhost:8000/` en navegador.

Si antes falló, **sí: debes repetir los comandos**, pero asegurándote de hacerlos en ese orden y dentro de la carpeta del proyecto.

---

## Antes de correr nada, verifica esto:

1. **Tienes Python instalado**
   - `python --version`
   - si falla: prueba `python3 --version` (Linux/Mac) o `py --version` (Windows)

2. **Estás parado en la carpeta del proyecto**
   - `pwd` (Linux/Mac)
   - `Get-Location` (PowerShell)

3. **Instala/activa un entorno virtual** (si no activas el entorno, `pip`/`uvicorn` suelen fallar)

### Comprobación mínima para saber si quedó funcionando

Cuando el servidor levanta bien, la terminal muestra algo como:

`Uvicorn running on http://0.0.0.0:8000`

Luego prueba:

- `http://localhost:8000/` (frontend)
- `http://localhost:8000/health` (debe devolver JSON)
- `http://localhost:8000/docs` (Swagger)

---

## ¿Cómo descargo los archivos del proyecto?

Perfecta pregunta. Tienes 2 formas simples:

### Opción 1 (la más fácil): descargar ZIP desde GitHub

1. En GitHub, entra al repositorio.
2. Haz clic en **Code** (botón verde).
3. Clic en **Download ZIP**.
4. Descomprime el ZIP en una carpeta de tu PC.
5. Abre una terminal dentro de esa carpeta (la que contiene `main.py` y `requirements.txt`).

### Opción 2 (recomendada): clonar con Git

```bash
git clone <URL_DEL_REPOSITORIO>
cd mcc-backend
```

> En `<URL_DEL_REPOSITORIO>` va el enlace del repo (por ejemplo HTTPS de GitHub).

### ¿Cómo verifico que descargué bien?

Dentro de la carpeta del proyecto, ejecuta:

```bash
# Linux/macOS
pwd
ls

# Windows PowerShell
Get-Location
dir
```

Debes ver archivos como `main.py`, `requirements.txt`, `README.md` y carpeta `frontend/`.

---

## Pasos simples (nivel principiante) para dejarla funcionando

Si es tu primera vez, sigue **exactamente** este orden:

1. **Descarga o abre este proyecto** en tu computadora.
2. **Abre una terminal dentro de la carpeta** `mcc-backend`.
3. **Verifica Python**:
   - Linux/Mac: `python3 --version`
   - Windows: `py --version`
4. **Crea entorno virtual** (aisla dependencias del proyecto).
5. **Activa el entorno virtual**.
6. **Instala dependencias** con `pip install -r requirements.txt`.
7. **Inicia el servidor** con `python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000`.
8. Abre en navegador:
   - `http://localhost:8000/` (frontend)
   - `http://localhost:8000/docs` (API)

Si ves en la terminal `Uvicorn running on ...`, la app ya está funcionando.

### Comandos para copiar y pegar

#### Linux/macOS

```bash
cd /ruta/a/mcc-backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Windows PowerShell

```powershell
cd C:\ruta\a\mcc-backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Setup según tu sistema

### Opción A — Linux / macOS (bash, zsh)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Opción B — Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> Si `Activate.ps1` da error de políticas, ejecuta **una vez**:
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

### Opción C — Windows CMD

```cmd
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## Abrir la app

Con el servidor levantado:

- Frontend demo: `http://localhost:8000/`
- Swagger API: `http://localhost:8000/docs`

---

## GitHub: diferencia entre crear repo y crear PR

Sí, puedes probar localmente con los comandos anteriores.

Sobre GitHub:

- **"Crear PR"** NO crea un repositorio nuevo.
- **"Crear PR"** abre una *Pull Request* para proponer cambios de una rama hacia otra dentro de un repo existente.
- Para crear un repositorio nuevo debes usar **New repository** en GitHub y luego subir tus archivos con `git push`.

Flujo recomendado si es tu primera vez:

1. Pruebas la app local con `uvicorn`.
2. Haces commit de tus cambios (`git add`, `git commit`).
3. Subes la rama a GitHub (`git push`).
4. Recién ahí usas **Create PR** para pedir merge de tu rama a `main`.

---

## Solución rápida de errores comunes

### 1) `python: command not found`
Usa `python3` (Linux/Mac) o `py` (Windows).

### 2) `uvicorn: command not found`
No está activo el entorno virtual o no se instaló dependencia.
- activa `.venv`
- usa `python -m uvicorn ...` en lugar de `uvicorn ...`

### 3) `No module named ...`
Faltan paquetes:
```bash
pip install -r requirements.txt
```

### 4) Puerto ocupado (`Address already in use`)
Cambia puerto:
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### 5) Estás en "softshell" y comandos cambian
No hay problema: la clave es usar `python -m ...` y entorno virtual activo.

---

## Endpoints API

### `GET /mcc/market-context`
Contexto multi-timeframe (`1D`, `4H`, `1H`, `15m`) con bias, trend, BOS, zonas y liquidez micro.

### `GET /mcc/signals`
Sugerencia simple según tendencia detectada: `side`, `entry`, `stop_loss`, `take_profit`, `risk_reward`.

### `POST /mcc/backtest`
Backtest SMA fast/slow.

Body ejemplo:

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "lookback_bars": 500,
  "fast_period": 20,
  "slow_period": 50,
  "fee_bps": 4.0
}
```

### `GET /health`
Chequeo básico de estado.

---

## Tests

```bash
python -m py_compile main.py
python -m unittest discover -s tests -p "test_*.py"
```
