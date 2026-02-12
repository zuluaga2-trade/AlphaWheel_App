# Changelog

## [Sin publicar] - 2026-02-12

### Añadido
- **Medidor de análisis del riesgo (gauge)** en screener y cuentas:
  - Semicírculo con eje de precios (escala numérica en el arco).
  - Tres agujas (Strike, BE, Precio) que atraviesan el ancho del arco; colores neón (naranja, gris, cyan).
  - Zonas de color: pérdida (rojo), banda BE (ámbar), ganancia (verde), con buen contraste sobre fondo oscuro.
  - Marco luminoso (cyan) alrededor del semicírculo.
  - DTE y estado (Favorable / Evaluar / Desfavorable) en el centro del gauge.
- **Columna "Acciones libres"** en la tabla de posiciones de cuentas (cockpit y main_app): muestra cuántas acciones del ticker no están comprometidas en CSP o CC.
- **Métrica "Cumplimiento"** bajo el gráfico en la pestaña Cuentas: porcentaje 0–100% que refleja el score del medidor (Favorable/Evaluar/Desfavorable).
- Módulo `app/position_chart_utils.py`: cálculo de score de riesgo (`risk_analysis_score`), gauge por eje de precios (`build_gauge_price_axis`), métricas para screener/posición y resúmenes copiables.

### Cambiado
- Análisis del riesgo: de "Salud de la posición" a **"Análisis del riesgo"** (Favorable/Desfavorable, Ganando/Perdiendo).
- Lógica del score basada en moneyness, DTE, P&L y earnings (opciones).
- Tutorial y textos de ayuda actualizados a "Análisis del riesgo".

### Técnico
- `build_gauge_price_axis(strike, be, precio, dte, status_label, ...)` para el medidor tipo reloj con agujas y zonas.
- Integración del gauge en: análisis de contrato Thinkorswim, ficha Sniper, fila del screener (cockpit) y detalle de posición en dashboard (cockpit y main_app).
