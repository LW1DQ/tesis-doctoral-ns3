#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging
from typing import Dict, List
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

class PerformanceAnalyzer:
    def __init__(self, simulation_dir: str):
        self.simulation_dir = Path(simulation_dir)
        self.results_dir = Path('post_processing/results')
        self.configs = ['no_mal_no_int', 'int_no_mal', 'mal_no_int', 'mal_int']
        self.protocols = ['AODV', 'OLSR', 'DSDV', 'DSR']
        
    def analyze_performance_metrics(self, metrics_data: Dict):
        """Analiza métricas relacionadas con rendimiento"""
        performance_metrics = {
            'throughput_promedio': 'Throughput de red',
            'delay_promedio': 'Latencia de red',
            'jitter_promedio': 'Jitter de red',
            'perdida_paquetes': 'Tasa de pérdida de paquetes',
            'pdr': 'Packet Delivery Ratio',
            'paquetes_totales': 'Número total de paquetes',
            'paquetes_perdidos': 'Número de paquetes perdidos',
            'numero_flujos': 'Número de flujos',
            'tiempo_simulacion': 'Tiempo de simulación'
        }
        
        for metric, description in performance_metrics.items():
            self._analyze_performance_metric(metrics_data, metric, description)
            
    def _analyze_performance_metric(self, metrics_data: Dict, metric: str, description: str):
        """Analiza una métrica específica de rendimiento"""
        # Crear DataFrame para análisis
        data = []
        for config in self.configs:
            for protocol in self.protocols:
                protocol_data = metrics_data[config][protocol]
                for run_name, run_data in protocol_data.items():
                    if metric in run_data.columns:
                        # Calcular el valor promedio para esta métrica
                        values = run_data[metric].dropna().values
                        if len(values) > 0:  # Solo agregar si hay valores no-NaN
                            value = np.mean(values)
                            data.append({
                                'config': config,
                                'protocol': protocol,
                                'run': run_name,
                                'value': value
                            })
        
        if not data:  # Si no hay datos, salir
            logging.warning(f"No se encontraron datos para la métrica {metric}")
            return
            
        df = pd.DataFrame(data)
        
        # Asegurarse de que el directorio de tablas existe
        tables_dir = self.results_dir / 'tables'
        tables_dir.mkdir(parents=True, exist_ok=True)
        
        # Análisis estadístico
        stats_by_config = df.groupby('config')['value'].agg(['mean', 'std', 'min', 'max'])
        stats_by_protocol = df.groupby('protocol')['value'].agg(['mean', 'std', 'min', 'max'])
        
        # Guardar estadísticas
        stats_by_config.to_csv(str(tables_dir / f'{metric}_by_config.csv'))
        stats_by_protocol.to_csv(str(tables_dir / f'{metric}_by_protocol.csv'))
        
        # Generar gráficos
        self._plot_performance_metric(df, metric, description)
        
    def _plot_performance_metric(self, df: pd.DataFrame, metric: str, description: str):
        """Genera gráficos para una métrica de rendimiento"""
        # Gráfico de barras por configuración
        fig = px.box(df, x='config', y='value', color='protocol',
                    title=f'{description} por Configuración y Protocolo')
        fig.write_html(str(self.results_dir / 'graphs' / f'{metric}_performance.html'))
        
        # Gráfico de violín
        plt.figure(figsize=(12, 6))
        sns.violinplot(data=df, x='config', y='value', hue='protocol')
        plt.title(f'Distribución de {description}')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(str(self.results_dir / 'graphs' / f'{metric}_violin.png'))
        plt.close()
        
    def analyze_efficiency(self, metrics_data: Dict):
        """Analiza la eficiencia de los protocolos"""
        efficiency_metrics = {
            'throughput_promedio': 'Eficiencia de throughput',
            'delay_promedio': 'Eficiencia de latencia',
            'perdida_paquetes': 'Eficiencia de pérdida de paquetes',
            'pdr': 'Eficiencia de PDR'
        }
        
        for metric, description in efficiency_metrics.items():
            try:
                self._analyze_efficiency(metrics_data, metric, description)
            except Exception as e:
                logging.error(f"Error al analizar la eficiencia de {metric}: {str(e)}")
                continue
            
    def _analyze_efficiency(self, metrics_data: Dict, metric: str, description: str):
        """Analiza la eficiencia de una métrica específica"""
        try:
            efficiency_data = []
            
            # Obtener el valor base (no_mal_no_int)
            base_values = []
            if 'no_mal_no_int' in metrics_data:
                for protocol in self.protocols:
                    if protocol in metrics_data['no_mal_no_int']:
                        for run_data in metrics_data['no_mal_no_int'][protocol].values():
                            if isinstance(run_data, pd.DataFrame) and metric in run_data.columns:
                                values = run_data[metric].dropna().values
                                if len(values) > 0:
                                    base_values.extend(values)
            
            if not base_values:
                logging.warning(f"No hay valores base válidos para {metric}, saltando análisis de eficiencia")
                return
            
            # Validación de valores base
            base_values = np.array(base_values)
            if np.all(base_values == 0):
                logging.warning(f"Todos los valores base para {metric} son cero, usando valor base de 1")
                base_mean = 1.0
                base_std = 1.0
            else:
                base_mean = float(np.mean(base_values))
                base_std = float(np.std(base_values))
                if base_std == 0:
                    logging.warning(f"Desviación estándar cero para valores base de {metric}, usando valor base de 1")
                    base_std = 1.0
            
            # Calcular eficiencia para cada configuración y protocolo
            for config_name in self.configs:
                if config_name in metrics_data:
                    for protocol in self.protocols:
                        if protocol in metrics_data[config_name]:
                            values = []
                            for run_data in metrics_data[config_name][protocol].values():
                                if isinstance(run_data, pd.DataFrame) and metric in run_data.columns:
                                    run_values = run_data[metric].dropna().values
                                    if len(run_values) > 0:
                                        values.extend(run_values)
                            
                            if values:
                                # Validación de valores
                                values = np.array(values)
                                if np.all(values == 0):
                                    logging.warning(f"Todos los valores para {metric} en {config_name}/{protocol} son cero")
                                    continue
                                    
                                mean_value = float(np.mean(values))
                                std_value = float(np.std(values)) if len(values) > 1 else 1.0
                                
                                # Calcular eficiencia como la relación entre la media y la desviación estándar
                                efficiency = mean_value / std_value if std_value != 0 else 0.0
                                
                                efficiency_data.append({
                                    'Configuración': config_name,
                                    'Protocolo': protocol,
                                    'Eficiencia': efficiency
                                })
            
            if not efficiency_data:
                logging.warning(f"No hay datos suficientes para calcular eficiencia de {metric}")
                return
            
            # Crear DataFrame y guardar resultados
            df = pd.DataFrame(efficiency_data)
            
            # Asegurarse de que los directorios existen
            tables_dir = self.results_dir / 'tables'
            graphs_dir = self.results_dir / 'graphs'
            
            for directory in [tables_dir, graphs_dir]:
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logging.error(f"Error al crear directorio {directory}: {str(e)}")
                    return
            
            # Guardar resultados
            try:
                df.to_csv(tables_dir / f'{metric}_efficiency.csv', index=False)
            except Exception as e:
                logging.error(f"Error al guardar resultados de eficiencia para {metric}: {str(e)}")
                return
            
            # Generar gráfico solo si hay datos
            if not df.empty:
                try:
                    fig = px.bar(df, x='Protocolo', y='Eficiencia', color='Configuración',
                               title=f'Eficiencia de {description}',
                               labels={'Eficiencia': f'Eficiencia de {description}',
                                     'Protocolo': 'Protocolo de Enrutamiento'})
                    
                    fig.write_html(str(graphs_dir / f'{metric}_efficiency.html'))
                except Exception as e:
                    logging.error(f"Error al generar gráfico de eficiencia para {metric}: {str(e)}")
            
        except Exception as e:
            logging.error(f"Error en análisis de eficiencia para {metric}: {str(e)}")
            raise
        
    def analyze_scalability(self, metrics_data: Dict):
        """Analiza la escalabilidad de la red"""
        try:
            scalability_data = []
            
            for config_name, config_data in metrics_data.items():
                for protocol, protocol_data in config_data.items():
                    # Obtener datos de número de flujos y throughput
                    flows = []
                    throughputs = []
                    
                    for run_data in protocol_data.values():
                        if isinstance(run_data, pd.DataFrame):
                            if 'numero_flujos' in run_data.columns and 'throughput_promedio' in run_data.columns:
                                flows.extend(run_data['numero_flujos'].dropna().values)
                                throughputs.extend(run_data['throughput_promedio'].dropna().values)
                    
                    if flows and throughputs:
                        # Calcular la relación entre throughput y número de flujos
                        throughput_per_flow = np.mean(throughputs) / np.mean(flows) if np.mean(flows) != 0 else 0
                        
                        scalability_data.append({
                            'Configuración': config_name,
                            'Protocolo': protocol,
                            'Throughput por Flujo': throughput_per_flow
                        })
            
            if not scalability_data:
                logging.warning("No hay datos suficientes para analizar la escalabilidad")
                return
            
            # Crear DataFrame y guardar resultados
            df = pd.DataFrame(scalability_data)
            
            # Asegurarse de que el directorio existe
            tables_dir = self.results_dir / 'tables'
            tables_dir.mkdir(parents=True, exist_ok=True)
            
            # Guardar resultados
            df.to_csv(tables_dir / 'scalability_analysis.csv', index=False)
            
            # Generar gráfico solo si hay datos
            if not df.empty:
                try:
                    fig = px.bar(df, x='Protocolo', y='Throughput por Flujo', color='Configuración',
                               title='Análisis de Escalabilidad',
                               labels={'Throughput por Flujo': 'Throughput por Flujo',
                                     'Protocolo': 'Protocolo de Enrutamiento'})
                    
                    # Asegurarse de que el directorio existe
                    graphs_dir = self.results_dir / 'graphs'
                    graphs_dir.mkdir(parents=True, exist_ok=True)
                    
                    fig.write_html(str(graphs_dir / 'scalability_analysis.html'))
                except Exception as e:
                    logging.error(f"Error al generar gráfico de escalabilidad: {str(e)}")
            
        except Exception as e:
            logging.error(f"Error en el análisis de escalabilidad: {str(e)}")
            raise

    def generate_performance_report(self, metrics_data: Dict):
        """Genera un reporte de rendimiento"""
        try:
            # Asegurarse de que los directorios necesarios existen
            self.results_dir.mkdir(parents=True, exist_ok=True)
            (self.results_dir / 'tables').mkdir(exist_ok=True)
            (self.results_dir / 'graphs').mkdir(exist_ok=True)
            (self.results_dir / 'reports').mkdir(exist_ok=True)
            
            # Análisis de métricas de rendimiento
            try:
                self.analyze_performance_metrics(metrics_data)
            except Exception as e:
                logging.error(f"Error en el análisis de métricas de rendimiento: {str(e)}")
            
            # Análisis de eficiencia
            try:
                self.analyze_efficiency(metrics_data)
            except Exception as e:
                logging.error(f"Error en el análisis de eficiencia: {str(e)}")
            
            # Análisis de escalabilidad
            try:
                self.analyze_scalability(metrics_data)
            except Exception as e:
                logging.error(f"Error en el análisis de escalabilidad: {str(e)}")
            
            # Generar reporte PDF
            try:
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet
                
                report_path = str(self.results_dir / 'reports' / 'performance_report.pdf')
                doc = SimpleDocTemplate(report_path, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []
                
                # Título
                elements.append(Paragraph("Análisis de Rendimiento", styles['Title']))
                elements.append(Spacer(1, 12))
                
                # Resumen de rendimiento
                elements.append(Paragraph("Resumen de Rendimiento", styles['Heading1']))
                elements.append(Paragraph(
                    "Este reporte presenta un análisis detallado del rendimiento de la red "
                    "bajo diferentes protocolos de enrutamiento y condiciones de red.",
                    styles['Normal']
                ))
                elements.append(Spacer(1, 12))
                
                # Conclusiones de rendimiento
                elements.append(Paragraph("Conclusiones de Rendimiento", styles['Heading1']))
                elements.append(Paragraph(
                    "Basado en el análisis de los datos, se pueden extraer las siguientes conclusiones "
                    "sobre el rendimiento de la red:",
                    styles['Normal']
                ))
                
                # Generar conclusiones automáticamente
                for metric in ['throughput_promedio', 'delay_promedio', 'perdida_paquetes', 'pdr']:
                    try:
                        metric_file = self.results_dir / 'tables' / f'{metric}_by_protocol.csv'
                        if metric_file.exists():
                            metric_data = pd.read_csv(metric_file)
                            if not metric_data.empty:
                                best_protocol = metric_data.loc[metric_data['mean'].idxmax() if metric == 'throughput_promedio' 
                                                              else metric_data['mean'].idxmin()]
                                
                                elements.append(Paragraph(
                                    f"• Para {metric}: El protocolo {best_protocol.name} mostró el mejor rendimiento "
                                    f"con un valor promedio de {best_protocol['mean']:.2f}.",
                                    styles['Normal']
                                ))
                    except Exception as e:
                        logging.error(f"Error al generar conclusión para {metric}: {str(e)}")
                        continue
                
                doc.build(elements)
                
            except Exception as e:
                logging.error(f"Error al generar el reporte PDF: {str(e)}")
                
        except Exception as e:
            logging.error(f"Error general en la generación del reporte: {str(e)}")
            raise

    def _plot_correlation_heatmap(self, metrics_data: Dict, metric: str):
        """Genera mapa de calor de correlaciones"""
        try:
            correlation_data = []
            min_data_points = 3  # Mínimo número de puntos de datos para correlación
            
            for config in self.configs:
                if config not in metrics_data:
                    continue
                    
                for protocol in self.protocols:
                    if protocol not in metrics_data[config]:
                        continue
                        
                    protocol_data = metrics_data[config][protocol]
                    for run_data in protocol_data.values():
                        if not isinstance(run_data, pd.DataFrame):
                            continue
                            
                        # Verificar que todas las métricas necesarias estén presentes
                        if not all(m in run_data.columns for m in self.metrics.keys()):
                            continue
                            
                        # Filtrar columnas y manejar valores NaN
                        data = run_data[self.metrics.keys()].fillna(method='ffill').fillna(method='bfill').fillna(0)
                        
                        # Verificar que hay suficientes datos no-NaN
                        if data.notna().sum().min() >= min_data_points:
                            try:
                                corr = data.corr()
                                if not corr.isna().all().all():
                                    correlation_data.append(corr)
                            except Exception as e:
                                logging.warning(f"Error al calcular correlación para {config}/{protocol}: {str(e)}")
                                continue
            
            if correlation_data:
                # Calcular correlación promedio
                mean_correlation = pd.concat(correlation_data).groupby(level=0).mean()
                
                # Verificar que hay datos válidos para graficar
                if not mean_correlation.isna().all().all():
                    # Asegurarse de que el directorio existe
                    graphs_dir = self.results_dir / 'graphs'
                    graphs_dir.mkdir(parents=True, exist_ok=True)
                    
                    plt.figure(figsize=(10, 8))
                    sns.heatmap(mean_correlation, annot=True, cmap='coolwarm', center=0, 
                              mask=mean_correlation.isna(), fmt='.2f')
                    plt.title(f'Correlación entre Métricas para {metric}')
                    plt.tight_layout()
                    plt.savefig(str(graphs_dir / f'{metric}_correlation.png'))
                    plt.close()
                else:
                    logging.warning(f"No hay datos válidos para generar el mapa de calor de correlación para {metric}")
            else:
                logging.warning(f"No hay suficientes datos para generar el mapa de calor de correlación para {metric}")
                
        except Exception as e:
            logging.error(f"Error al generar mapa de calor de correlación para {metric}: {str(e)}")

if __name__ == "__main__":
    import sys
    from run_analysis import SimulationAnalyzer
    
    if len(sys.argv) != 2:
        print("Uso: python performance_analysis.py <directorio_simulacion>")
        sys.exit(1)
    
    # Cargar datos usando el analizador principal
    analyzer = SimulationAnalyzer(sys.argv[1])
    metrics_data = analyzer.load_metrics()
    
    # Realizar análisis de rendimiento
    performance_analyzer = PerformanceAnalyzer(sys.argv[1])
    performance_analyzer.generate_performance_report(metrics_data) 