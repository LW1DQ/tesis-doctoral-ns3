import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import logging
import json
from concurrent.futures import ThreadPoolExecutor
import shutil
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('post_processing.log'),
        logging.StreamHandler()
    ]
)

# Configuraciones y rutas
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
configs = ['mal_int', 'mal_no_int', 'int_no_mal', 'no_mal_no_int']
protocols = ['AODV', 'OLSR', 'DSDV', 'DSR']
num_runs = 10

# Crear directorio de resultados
results_dir = os.path.join(base_dir, 'post_processing', 'results')
os.makedirs(results_dir, exist_ok=True)

def validate_metrics_file(file_path):
    """Valida el archivo de métricas"""
    try:
        if not os.path.exists(file_path):
            return False
        
        df = pd.read_csv(file_path)
        required_columns = [
            'throughput_promedio', 'delay_promedio', 'jitter_promedio',
            'perdida_paquetes', 'pdr', 'paquetes_totales'
        ]
        
        return all(col in df.columns for col in required_columns)
    except Exception as e:
        logging.error(f"Error al validar archivo de métricas {file_path}: {str(e)}")
        return False

def load_metrics(config, protocol):
    """Carga las métricas de una configuración y protocolo"""
    try:
        metrics_data = []
        for run in range(1, num_runs + 1):
            metrics_file = os.path.join(base_dir, config, protocol, f'run{run}', 'metrics', 'metrics.csv')
            if validate_metrics_file(metrics_file):
                df = pd.read_csv(metrics_file)
                metrics_data.append(df)
            else:
                logging.warning(f"Archivo de métricas inválido o no encontrado: {metrics_file}")
        
        if metrics_data:
            return pd.concat(metrics_data, ignore_index=True)
        return None
    except Exception as e:
        logging.error(f"Error al cargar métricas para {config}/{protocol}: {str(e)}")
        return None

def calculate_statistics(df):
    """Calcula estadísticas de las métricas"""
    try:
        if df is None or df.empty:
            return None
        
        stats = {}
        metrics = [
            'throughput_promedio', 'delay_promedio', 'jitter_promedio',
            'perdida_paquetes', 'pdr', 'paquetes_totales'
        ]
        
        for metric in metrics:
            if metric in df.columns:
                stats[metric] = {
                    'mean': float(df[metric].mean()),
                    'std': float(df[metric].std()),
                    'min': float(df[metric].min()),
                    'max': float(df[metric].max()),
                    'median': float(df[metric].median())
                }
        
        return stats
    except Exception as e:
        logging.error(f"Error al calcular estadísticas: {str(e)}")
        return None

def generate_plots(config, protocol, df, stats):
    """Genera gráficos para una configuración y protocolo"""
    try:
        if df is None or df.empty:
            return
        
        # Crear directorio para gráficos
        plots_dir = os.path.join(results_dir, 'graphs', config, protocol)
        os.makedirs(plots_dir, exist_ok=True)
        
        # Gráfico de throughput
        plt.figure(figsize=(10, 6))
        sns.boxplot(data=df, y='throughput_promedio')
        plt.title(f'Throughput Distribution - {config}/{protocol}')
        plt.ylabel('Throughput (kbps)')
        plt.grid(True)
        plt.savefig(os.path.join(plots_dir, 'throughput_distribution.png'))
        plt.close()
        
        # Gráfico de delay
        plt.figure(figsize=(10, 6))
        sns.boxplot(data=df, y='delay_promedio')
        plt.title(f'Delay Distribution - {config}/{protocol}')
        plt.ylabel('Delay (s)')
        plt.grid(True)
        plt.savefig(os.path.join(plots_dir, 'delay_distribution.png'))
        plt.close()
        
        # Gráfico de PDR
        plt.figure(figsize=(10, 6))
        sns.boxplot(data=df, y='pdr')
        plt.title(f'PDR Distribution - {config}/{protocol}')
        plt.ylabel('PDR (%)')
        plt.grid(True)
        plt.savefig(os.path.join(plots_dir, 'pdr_distribution.png'))
        plt.close()
        
        # Gráfico de correlación
        plt.figure(figsize=(12, 8))
        correlation_matrix = df[['throughput_promedio', 'delay_promedio', 'jitter_promedio', 'pdr']].corr()
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0)
        plt.title(f'Correlation Matrix - {config}/{protocol}')
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, 'correlation_matrix.png'))
        plt.close()
        
    except Exception as e:
        logging.error(f"Error al generar gráficos para {config}/{protocol}: {str(e)}")

def process_config_protocol(config, protocol):
    """Procesa una configuración y protocolo específicos"""
    try:
        logging.info(f"Procesando {config}/{protocol}")
        
        # Cargar métricas
        df = load_metrics(config, protocol)
        if df is None:
            logging.warning(f"No hay métricas disponibles para {config}/{protocol}")
            return
        
        # Calcular estadísticas
        stats = calculate_statistics(df)
        if stats is None:
            logging.warning(f"No se pudieron calcular estadísticas para {config}/{protocol}")
            return
        
        # Generar gráficos
        generate_plots(config, protocol, df, stats)
        
        # Guardar estadísticas
        stats_file = os.path.join(results_dir, 'stats', f'{config}_{protocol}_stats.json')
        os.makedirs(os.path.dirname(stats_file), exist_ok=True)
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=4)
        
        logging.info(f"Procesamiento completado para {config}/{protocol}")
        
    except Exception as e:
        logging.error(f"Error al procesar {config}/{protocol}: {str(e)}")

def backup_results():
    """Crea un respaldo de los resultados"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        backup_dir = os.path.join(base_dir, 'post_processing', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_file = os.path.join(backup_dir, f'results_backup_{timestamp}.tar.gz')
        shutil.make_archive(
            backup_file.replace('.tar.gz', ''),
            'gztar',
            results_dir
        )
        logging.info(f"Respaldo creado: {backup_file}")
    except Exception as e:
        logging.error(f"Error al crear respaldo: {str(e)}")

def main():
    """Función principal"""
    try:
        logging.info("Iniciando post-procesamiento")
        
        # Crear estructura de directorios
        os.makedirs(os.path.join(results_dir, 'graphs'), exist_ok=True)
        os.makedirs(os.path.join(results_dir, 'stats'), exist_ok=True)
        
        # Procesar configuraciones y protocolos en paralelo
        with ThreadPoolExecutor(max_workers=4) as executor:
            for config in configs:
                for protocol in protocols:
                    executor.submit(process_config_protocol, config, protocol)
        
        # Crear respaldo de resultados
        backup_results()
        
        logging.info("Post-procesamiento completado exitosamente")
        
    except Exception as e:
        logging.error(f"Error en el post-procesamiento: {str(e)}")

if __name__ == '__main__':
    main()