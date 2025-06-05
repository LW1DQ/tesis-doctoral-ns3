#!/usr/bin/env python3

import os
import sys
import logging
from pathlib import Path
import argparse
from datetime import datetime
import shutil

from run_analysis import SimulationAnalyzer
from security_analysis import SecurityAnalyzer
from performance_analysis import PerformanceAnalyzer

def setup_logging():
    """Configura el sistema de logging"""
    try:
        log_dir = Path('post_processing/logs')
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f'post_processing_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        logging.info(f"Logging configurado en {log_file}")
    except Exception as e:
        print(f"Error al configurar logging: {str(e)}")
        sys.exit(1)

def create_results_structure():
    """Crea la estructura de directorios para los resultados"""
    try:
        results_dir = Path('post_processing/results')
        dirs = [
            results_dir / 'tables',
            results_dir / 'graphs',
            results_dir / 'reports',
            results_dir / 'raw_data'
        ]
        
        for dir_path in dirs:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logging.info(f"Directorio creado/verificado: {dir_path}")
            except Exception as e:
                logging.error(f"Error al crear directorio {dir_path}: {str(e)}")
                raise
    except Exception as e:
        logging.error(f"Error al crear estructura de directorios: {str(e)}")
        raise

def backup_raw_data(simulation_dir: str):
    """Hace una copia de seguridad de los datos originales"""
    try:
        src_dir = Path(simulation_dir)
        if not src_dir.exists():
            raise FileNotFoundError(f"El directorio de origen {simulation_dir} no existe")
            
        dst_dir = Path('post_processing/results/raw_data')
        dst_dir.mkdir(parents=True, exist_ok=True)
        
        # Lista de directorios a copiar
        dirs_to_copy = ['mal_int', 'mal_no_int', 'int_no_mal', 'no_mal_no_int']
        
        for dir_name in dirs_to_copy:
            src = src_dir / dir_name
            dst = dst_dir / dir_name
            
            if src.exists():
                try:
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                    logging.info(f"Directorio {dir_name} copiado exitosamente")
                except Exception as e:
                    logging.error(f"Error al copiar directorio {dir_name}: {str(e)}")
                    raise
            else:
                logging.warning(f"El directorio {dir_name} no existe en la ubicación de origen")
    except Exception as e:
        logging.error(f"Error en backup de datos: {str(e)}")
        raise

def validate_simulation_dir(simulation_dir: str):
    """Valida que el directorio de simulación tenga la estructura correcta"""
    try:
        required_dirs = ['mal_int', 'mal_no_int', 'int_no_mal', 'no_mal_no_int']
        required_protocols = ['AODV', 'OLSR', 'DSDV', 'DSR']
        
        sim_dir = Path(simulation_dir)
        if not sim_dir.exists():
            raise FileNotFoundError(f"El directorio de simulación {simulation_dir} no existe")
            
        for config in required_dirs:
            config_dir = sim_dir / config
            if not config_dir.exists():
                raise FileNotFoundError(f"Falta el directorio de configuración {config}")
                
            for protocol in required_protocols:
                protocol_dir = config_dir / protocol
                if not protocol_dir.exists():
                    logging.warning(f"Falta el directorio del protocolo {protocol} en {config}")
                    continue
                    
                # Verificar que haya al menos una ejecución
                runs = list(protocol_dir.glob('run*'))
                if not runs:
                    logging.warning(f"No se encontraron ejecuciones para {protocol} en {config}")
                    
        return True
    except Exception as e:
        logging.error(f"Error al validar directorio de simulación: {str(e)}")
        return False

def run_analysis(simulation_dir: str):
    """Ejecuta todo el proceso de análisis"""
    logging.info("Iniciando proceso de post-procesamiento...")
    
    try:
        # Validar directorio de simulación
        if not validate_simulation_dir(simulation_dir):
            raise ValueError("El directorio de simulación no tiene la estructura correcta")
        
        # Crear estructura de directorios
        create_results_structure()
        
        # Hacer backup de datos originales
        backup_raw_data(simulation_dir)
        
        # Cargar datos
        analyzer = SimulationAnalyzer(simulation_dir)
        metrics_data = analyzer.load_metrics()
        
        # Verificar si hay datos cargados
        if not any(metrics_data.values()):
            raise ValueError("No se encontraron datos de métricas en ninguna configuración")
        
        # Ejecutar análisis principal
        logging.info("Ejecutando análisis principal...")
        analyzer.run_analysis()
        
        # Ejecutar análisis de seguridad
        logging.info("Ejecutando análisis de seguridad...")
        security_analyzer = SecurityAnalyzer(simulation_dir)
        security_analyzer.generate_security_report(metrics_data)
        
        # Ejecutar análisis de rendimiento
        logging.info("Ejecutando análisis de rendimiento...")
        performance_analyzer = PerformanceAnalyzer(simulation_dir)
        performance_analyzer.generate_performance_report(metrics_data)
        
        logging.info("Proceso de post-procesamiento completado exitosamente")
        
    except Exception as e:
        logging.error(f"Error durante el análisis: {str(e)}")
        raise

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Post-procesamiento de simulaciones IoT')
    parser.add_argument('simulation_dir', help='Directorio de las simulaciones a analizar')
    args = parser.parse_args()
    
    try:
        # Configurar logging
        setup_logging()
        
        # Ejecutar análisis
        run_analysis(args.simulation_dir)
    except Exception as e:
        logging.error(f"Error fatal: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 