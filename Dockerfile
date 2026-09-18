# Imagen liviana -- con min-instances=0, el tamaño de la imagen impacta directamente
# el cold start (ver PKB_Unidad5_Verificacion_Sesion_20260908.md, sección de costos/Cloud Run).
FROM python:3.12-slim

# libgomp1: XGBoost depende de OpenMP para paralelismo interno -- no viene por defecto
# en la imagen slim, hay que instalarlo explícitamente o el import de xgboost falla.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements ANTES que el código -- así Docker cachea esta capa y no
# reinstala todas las dependencias cada vez que solo cambia el código de app/.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Cloud Run espera que el contenedor escuche en el puerto 8080 por defecto.
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
