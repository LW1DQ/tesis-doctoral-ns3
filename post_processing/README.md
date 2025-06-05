# Sistema de Post-Procesamiento para Simulaciones IoT

Este sistema realiza el análisis y post-procesamiento de los resultados de simulaciones de redes IoT realizadas con NS-3. El sistema genera análisis detallados, gráficos y reportes sobre el rendimiento, seguridad y eficiencia de diferentes protocolos de enrutamiento.

## Estructura del Sistema

```
post_processing/
├── scripts/
│   ├── main.py              # Script principal
│   ├── run_analysis.py      # Análisis general
│   ├── security_analysis.py # Análisis de seguridad
│   └── performance_analysis.py # Análisis de rendimiento
├── results/
│   ├── tables/             # Tablas de resultados
│   ├── graphs/             # Gráficos generados
│   ├── reports/            # Reportes PDF
│   └── raw_data/           # Copia de datos originales
└── logs/                   # Logs del sistema
```

## Características

### Análisis General
- Estadísticas descriptivas de todas las métricas
- Gráficos comparativos entre protocolos
- Análisis de tendencias temporales
- Correlaciones entre métricas

### Análisis de Seguridad
- Impacto de nodos maliciosos
- Análisis de interferencias
- Métricas de seguridad por protocolo
- Reporte detallado de seguridad

### Análisis de Rendimiento
- Métricas de throughput
- Análisis de latencia y jitter
- Consumo de energía
- Eficiencia y escalabilidad

## Requisitos

- Python 3.8 o superior
- Dependencias listadas en `requirements.txt`

## Instalación

1. Crear un entorno virtual (opcional pero recomendado):
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

## Uso

Para ejecutar el análisis completo:

```bash
python scripts/main.py <directorio_simulacion>
```

Donde `<directorio_simulacion>` es la ruta al directorio que contiene los resultados de las simulaciones.

## Resultados

El sistema genera los siguientes tipos de resultados:

### Tablas
- Estadísticas resumen por protocolo y configuración
- Métricas de rendimiento
- Análisis de seguridad
- Eficiencia y escalabilidad

### Gráficos
- Gráficos de cajas para comparación de protocolos
- Gráficos de líneas para tendencias temporales
- Mapas de calor para correlaciones
- Gráficos de violín para distribuciones
- Gráficos interactivos en formato HTML

### Reportes PDF
- Reporte general de análisis
- Reporte de seguridad
- Reporte de rendimiento

## Métricas Analizadas

### Métricas de Rendimiento
- Throughput (Kbps)
- Latencia (ms)
- Jitter (ms)
- Pérdida de paquetes (%)
- Consumo de energía (J)
- Overhead de enrutamiento (paquetes)

### Métricas de Seguridad
- Tasa de pérdida de paquetes
- Sobrecarga de enrutamiento
- Latencia de red
- Impacto de ataques

### Métricas de Eficiencia
- Eficiencia de throughput
- Eficiencia energética
- Eficiencia de enrutamiento
- Escalabilidad

## Contribución

Para contribuir al proyecto:

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo LICENSE para más detalles. 