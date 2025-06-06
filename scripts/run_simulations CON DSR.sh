#!/bin/bash

# Configuración inicial
N_FIXED_NODES=20
N_MOBILE_NODES=10
SIM_TIME=60
NUM_RUNS=10

# Configuraciones de nodos maliciosos e interferentes
CONFIGS=(
    "no_mal_no_int:0:0"
    "int_no_mal:0:3"
    "mal_no_int:2:0"
    "mal_int:2:3"
)

# Protocolos de enrutamiento
PROTOCOLS=("AODV" "OLSR" "DSDV" "DSR")

# Función para verificar dependencias
check_dependencies() {
    echo "Verificando dependencias..."
    # Verificar si estamos en el directorio correcto de ns-3
    if [ ! -f "./ns3" ]; then
        echo "Error: No se encuentra el ejecutable ns3 en el directorio actual"
        echo "Asegúrate de ejecutar este script desde el directorio ns-3-dev"
        exit 1
    fi
    
    command -v python3 >/dev/null 2>&1 || { echo "Error: python3 no está instalado"; exit 1; }
    echo "Todas las dependencias están instaladas."
}

# Función para verificar espacio en disco
check_disk_space() {
    echo "Verificando espacio en disco..."
    local required_space=$((N_FIXED_NODES * N_MOBILE_NODES * NUM_RUNS * 100)) # estimación en KB
    local available_space=$(df -k "$SIMULATION_DIR" | awk 'NR==2 {print $4}')
    if [ "$available_space" -lt "$required_space" ]; then
        echo "Error: Espacio insuficiente en disco. Se requieren al menos $required_space KB"
        exit 1
    fi
    echo "Espacio en disco suficiente."
}

# Función para monitorear recursos
monitor_resources() {
    while true; do
        echo "$(date) - CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')% - Mem: $(free -m | awk 'NR==2{printf "%.2f%%", $3*100/$2 }')"
        sleep 60
    done
}

# Función para respaldo de resultados
backup_results() {
    echo "Creando respaldo de resultados..."
    tar -czf "${SIMULATION_DIR}_backup_$(date +%Y%m%d_%H%M).tar.gz" "$SIMULATION_DIR"
    echo "Respaldo creado: ${SIMULATION_DIR}_backup_$(date +%Y%m%d_%H%M).tar.gz"
}

# Función para limpiar archivos temporales
cleanup() {
    echo "Limpiando archivos temporales..."
    rm -f iot_simulation_*.pcap
    rm -rf "$OUTPUT_DIR"
}

# Configurar trap para limpieza
trap cleanup EXIT

# Crear directorio de simulación con timestamp
SIMULATION_DIR="/home/diego/Descargas/simulacion_$(date +%Y%m%d_%H%M)"
mkdir -p "$SIMULATION_DIR"
if [ ! -w "$SIMULATION_DIR" ]; then
    echo "Error: No se tienen permisos de escritura en $SIMULATION_DIR" >&2
    exit 1
fi

# Crear estructura de directorios
mkdir -p "$SIMULATION_DIR/scripts"
mkdir -p "$SIMULATION_DIR/logs"
echo "Directorio de simulación: $SIMULATION_DIR"

# Verificar dependencias y espacio
check_dependencies
check_disk_space

# Copiar scripts al directorio scripts/
cp run_simulations.sh "$SIMULATION_DIR/scripts/"
cp scratch/simulacioniot.cc "$SIMULATION_DIR/scripts/"
cp manual_metrics_dsr.py "$SIMULATION_DIR/scripts/"

# Iniciar monitoreo de recursos en segundo plano
monitor_resources &
MONITOR_PID=$!

# Iterar sobre cada configuración
for config in "${CONFIGS[@]}"; do
    # Extraer nombre de configuración, nodos maliciosos e interferentes
    CONFIG_NAME=$(echo "$config" | cut -d':' -f1)
    N_MALICIOUS_NODES=$(echo "$config" | cut -d':' -f2)
    N_INTERFERING_NODES=$(echo "$config" | cut -d':' -f3)

    # Iterar sobre cada protocolo
    for protocol in "${PROTOCOLS[@]}"; do
        # Iterar sobre cada corrida
        for run in $(seq 1 $NUM_RUNS); do
            # Definir semilla para la corrida
            SEED=$((1000 + run))

            # Definir directorio de salida temporal
            OUTPUT_DIR="$SIMULATION_DIR/raw_data_${CONFIG_NAME}_${protocol}_run${run}"
            NEW_DIR="$SIMULATION_DIR/$CONFIG_NAME/$protocol/run$run"
            
            echo "Ejecutando simulación: Config=$CONFIG_NAME, Protocol=$protocol, Run=$run, Seed=$SEED"
            
            # Ejecutar la simulación
            ./ns3 run "scratch/simulacioniot \
                --nFixedNodes=$N_FIXED_NODES \
                --nMobileNodes=$N_MOBILE_NODES \
                --nMaliciousNodes=$N_MALICIOUS_NODES \
                --nInterferingNodes=$N_INTERFERING_NODES \
                --simTime=$SIM_TIME \
                --routingProtocol=$protocol \
                --configName=$CONFIG_NAME \
                --outputDir=$OUTPUT_DIR \
                --seed=$SEED"
            
            # Crear directorios necesarios
            mkdir -p "$NEW_DIR/pcap"
            mkdir -p "$NEW_DIR/metrics"
            mkdir -p "$NEW_DIR/node_metadata"
            mkdir -p "$NEW_DIR/routing_logs"
            
            # Mover archivos PCAP
            mv iot_simulation_*.pcap "$NEW_DIR/pcap/" 2>/dev/null || true
            
            # Verificar archivos generados
            if [ ! -f "$OUTPUT_DIR/metrics/metrics.csv" ]; then
                echo "Error: Falta metrics.csv en $OUTPUT_DIR" >> "$SIMULATION_DIR/logs/error_log.txt"
            fi
            if [ ! -f "$OUTPUT_DIR/node_metadata/nodes.csv" ]; then
                echo "Error: Falta nodes.csv en $OUTPUT_DIR" >> "$SIMULATION_DIR/logs/error_log.txt"
            fi
            if [ -z "$(ls -A "$OUTPUT_DIR/pcap")" ]; then
                echo "Error: Directorio pcap vacío en $OUTPUT_DIR" >> "$SIMULATION_DIR/logs/error_log.txt"
            fi
            if [ ! -f "$OUTPUT_DIR/routing_logs/routing_table_changes.csv" ]; then
                echo "Error: Falta routing_table_changes.csv en $OUTPUT_DIR/routing_logs" >> "$SIMULATION_DIR/logs/error_log.txt"
            fi
            
            # Mover archivos a la estructura final
            mv "$OUTPUT_DIR"/* "$NEW_DIR/" 2>/dev/null || true
            rm -rf "$OUTPUT_DIR"
            
            echo "Archivos procesados y movidos a: $NEW_DIR"
        done
    done
done

# Detener monitoreo de recursos
kill $MONITOR_PID

# Ejecutar el script de métricas manuales para DSR
if [ -f "$SIMULATION_DIR/scripts/manual_metrics_dsr.py" ]; then
    echo "Generando métricas manuales para DSR..."
    python3 "$SIMULATION_DIR/scripts/manual_metrics_dsr.py"
fi

# Crear respaldo de resultados
backup_results

echo "Simulación completada. Resultados en $SIMULATION_DIR"
echo "Log de errores en $SIMULATION_DIR/logs/error_log.txt"