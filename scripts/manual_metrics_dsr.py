import os
import pandas as pd
import numpy as np
from glob import glob
from datetime import datetime
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from concurrent.futures import ThreadPoolExecutor
import json

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dsr_metrics.log'),
        logging.StreamHandler()
    ]
)

# Configuraciones y rutas
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
configs = ['mal_int', 'mal_no_int', 'int_no_mal', 'no_mal_no_int']
protocol = 'DSR'
num_runs = 10

# Columnas del archivo de métricas
metrics_columns = [
    'timestamp','protocolo','nodos_fijos','nodos_moviles','nodos_maliciosos','nodos_interferentes',
    'throughput_promedio','throughput_maximo','delay_promedio','delay_maximo','delay_minimo',
    'jitter_promedio','perdida_paquetes','pdr','paquetes_totales','paquetes_perdidos','numero_flujos','tiempo_simulacion'
]

def validate_metadata(meta):
    """Valida y procesa los metadatos"""
    try:
        # Valores por defecto
        defaults = {
            'Nodos Fijos': 0,
            'Nodos Móviles': 0,
            'Nodos Maliciosos': 0,
            'Nodos Interferentes': 0,
            'Tiempo de Simulación': '60',
            'Protocolo de Enrutamiento': 'DSR',
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Validar y convertir valores
        validated = {}
        for key, default in defaults.items():
            value = meta.get(key, default)
            if key in ['Nodos Fijos', 'Nodos Móviles', 'Nodos Maliciosos', 'Nodos Interferentes']:
                try:
                    validated[key] = int(value)
                except ValueError:
                    logging.warning(f"Valor inválido para {key}: {value}, usando valor por defecto")
                    validated[key] = default
            elif key == 'Tiempo de Simulación':
                try:
                    # Extraer solo el número
                    tiempo = float(''.join([c for c in value if (c.isdigit() or c=='.')]))
                    validated[key] = tiempo
                except ValueError:
                    logging.warning(f"Valor inválido para tiempo de simulación: {value}, usando valor por defecto")
                    validated[key] = float(default)
            else:
                validated[key] = value
                
        return validated
    except Exception as e:
        logging.error(f"Error al validar metadatos: {str(e)}")
        return defaults

def validate_packet_data(df):
    """Valida los datos de paquetes"""
    try:
        required_columns = ['sim_time', 'packet_size', 'source_ip']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Columnas faltantes: {missing_columns}")
        return True
    except Exception as e:
        logging.error(f"Error al validar datos de paquetes: {str(e)}")
        return False

def calculate_additional_metrics(df):
    """Calcula métricas adicionales"""
    try:
        if df.empty:
            return {
                'packets_per_second': 0,
                'avg_packet_size': 0,
                'unique_destinations': 0
            }
        
        return {
            'packets_per_second': len(df) / df['sim_time'].max() if df['sim_time'].max() > 0 else 0,
            'avg_packet_size': df['packet_size'].mean(),
            'unique_destinations': len(df['dest_ip'].unique()) if 'dest_ip' in df.columns else 0
        }
    except Exception as e:
        logging.error(f"Error al calcular métricas adicionales: {str(e)}")
        return {
            'packets_per_second': 0,
            'avg_packet_size': 0,
            'unique_destinations': 0
        }

def generate_basic_plots(df, output_dir):
    """Genera gráficos básicos de análisis"""
    try:
        if df.empty:
            return
        
        # Crear directorio para gráficos si no existe
        os.makedirs(output_dir, exist_ok=True)
        
        # Gráfico de tráfico acumulado
        plt.figure(figsize=(10, 6))
        plt.plot(df['sim_time'], df['packet_size'].cumsum())
        plt.title('Cumulative Traffic Over Time')
        plt.xlabel('Simulation Time (s)')
        plt.ylabel('Cumulative Traffic (bytes)')
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, 'traffic_over_time.png'))
        plt.close()
        
        # Gráfico de distribución de tamaños de paquetes
        plt.figure(figsize=(10, 6))
        sns.histplot(data=df, x='packet_size', bins=30)
        plt.title('Packet Size Distribution')
        plt.xlabel('Packet Size (bytes)')
        plt.ylabel('Count')
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, 'packet_size_distribution.png'))
        plt.close()
        
        # Gráfico de throughput por intervalo
        df['interval'] = (df['sim_time'] / 1.0).astype(int)
        throughput = df.groupby('interval')['packet_size'].sum() * 8 / 1000  # kbps
        plt.figure(figsize=(10, 6))
        throughput.plot()
        plt.title('Throughput Over Time')
        plt.xlabel('Time Interval (s)')
        plt.ylabel('Throughput (kbps)')
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, 'throughput_over_time.png'))
        plt.close()
        
    except Exception as e:
        logging.error(f"Error al generar gráficos: {str(e)}")

def process_run(run_dir, config, run):
    """Procesa una ejecución individual"""
    try:
        metrics_dir = os.path.join(run_dir, 'metrics')
        os.makedirs(metrics_dir, exist_ok=True)
        
        # Leer y validar metadatos
        meta_path = os.path.join(run_dir, 'metadata.txt')
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    for line in f:
                        if ':' in line:
                            k, v = line.strip().split(':', 1)
                            meta[k.strip()] = v.strip()
            except Exception as e:
                logging.error(f"Error al leer metadatos en {meta_path}: {str(e)}")
        
        # Validar metadatos
        validated_meta = validate_metadata(meta)
        
        # Leer logs de paquetes
        logs_dir = os.path.join(run_dir, 'packet_logs')
        normal_path = os.path.join(logs_dir, 'packets_normal.csv')
        malicious_path = os.path.join(logs_dir, 'packets_malicious.csv')
        
        try:
            df_normal = pd.read_csv(normal_path) if os.path.exists(normal_path) else pd.DataFrame()
            df_mal = pd.read_csv(malicious_path) if os.path.exists(malicious_path) else pd.DataFrame()
        except Exception as e:
            logging.error(f"Error al leer logs de paquetes en {run_dir}: {str(e)}")
            df_normal = pd.DataFrame()
            df_mal = pd.DataFrame()
        
        # Solo analizamos tráfico normal para métricas de red
        df = df_normal.copy()
        
        if df.empty:
            logging.warning(f"No hay tráfico normal en {run_dir}, generando métricas con valores base")
            row = [
                validated_meta['Timestamp'], validated_meta['Protocolo de Enrutamiento'],
                validated_meta['Nodos Fijos'], validated_meta['Nodos Móviles'],
                validated_meta['Nodos Maliciosos'], validated_meta['Nodos Interferentes'],
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0,
                validated_meta['Tiempo de Simulación']
            ]
        else:
            try:
                # Validar datos de paquetes
                if not validate_packet_data(df):
                    raise ValueError("Datos de paquetes inválidos")
                
                # Ordenar por tiempo de simulación
                df = df.sort_values('sim_time')
                
                # Throughput promedio y máximo (kbps)
                total_bytes = df['packet_size'].sum()
                tiempo_sim = validated_meta['Tiempo de Simulación']
                throughput_promedio = (total_bytes * 8) / (tiempo_sim * 1000) if tiempo_sim > 0 else 0.0
                
                # Calcular throughput por intervalo de tiempo
                df['interval'] = (df['sim_time'] / 1.0).astype(int)  # Intervalos de 1 segundo
                throughput_por_intervalo = df.groupby('interval')['packet_size'].sum() * 8 / 1000  # kbps
                throughput_maximo = throughput_por_intervalo.max() if not throughput_por_intervalo.empty else 0.0
                
                # Delay (diferencia entre paquetes consecutivos)
                df['delay'] = df['sim_time'].diff()
                delays = df['delay'].dropna().values
                delay_promedio = float(np.mean(delays)) if len(delays) > 0 else 0.0
                delay_maximo = float(np.max(delays)) if len(delays) > 0 else 0.0
                delay_minimo = float(np.min(delays)) if len(delays) > 0 else 0.0
                
                # Jitter (variación del delay)
                jitter_promedio = float(np.mean(np.abs(np.diff(delays)))) if len(delays) > 1 else 0.0
                
                # Métricas de paquetes
                paquetes_totales = len(df)
                paquetes_perdidos = 0  # En DSR no tenemos información de paquetes perdidos
                perdida_paquetes = 0.0
                pdr = 100.0 if paquetes_totales > 0 else 0.0
                
                # Número de flujos (basado en IPs únicas)
                numero_flujos = len(df['source_ip'].unique())
                
                # Calcular métricas adicionales
                additional_metrics = calculate_additional_metrics(df)
                
                # Generar gráficos básicos
                plots_dir = os.path.join(metrics_dir, 'plots')
                generate_basic_plots(df, plots_dir)
                
                # Guardar métricas adicionales
                with open(os.path.join(metrics_dir, 'additional_metrics.json'), 'w') as f:
                    json.dump(additional_metrics, f, indent=4)
                
                row = [
                    validated_meta['Timestamp'], validated_meta['Protocolo de Enrutamiento'],
                    validated_meta['Nodos Fijos'], validated_meta['Nodos Móviles'],
                    validated_meta['Nodos Maliciosos'], validated_meta['Nodos Interferentes'],
                    throughput_promedio, throughput_maximo, delay_promedio, delay_maximo, delay_minimo,
                    jitter_promedio, perdida_paquetes, pdr, paquetes_totales, paquetes_perdidos,
                    numero_flujos, validated_meta['Tiempo de Simulación']
                ]
            except Exception as e:
                logging.error(f"Error al procesar métricas en {run_dir}: {str(e)}")
                return
        
        # Guardar métricas
        try:
            metrics_df = pd.DataFrame([row], columns=metrics_columns)
            metrics_path = os.path.join(metrics_dir, 'metrics.csv')
            metrics_df.to_csv(metrics_path, index=False)
            logging.info(f"Métricas guardadas exitosamente en {metrics_path}")
        except Exception as e:
            logging.error(f"Error al guardar métricas en {run_dir}: {str(e)}")
            
    except Exception as e:
        logging.error(f"Error general en el procesamiento de {run_dir}: {str(e)}")

def process_config(config):
    """Procesa todas las ejecuciones de una configuración"""
    for run in range(1, num_runs+1):
        run_dir = os.path.join(base_dir, config, protocol, f'run{run}')
        if os.path.exists(run_dir):
            logging.info(f'Procesando {run_dir}')
            process_run(run_dir, config, run)
        else:
            logging.warning(f'Directorio no encontrado: {run_dir}')

if __name__ == '__main__':
    logging.info("Iniciando procesamiento manual de métricas para DSR")
    
    # Procesar configuraciones en paralelo
    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(process_config, configs)
    
    logging.info('Procesamiento manual de métricas para DSR completado.')