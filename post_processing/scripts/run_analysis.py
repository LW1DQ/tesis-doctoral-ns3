#!/usr/bin/env python3

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import json
from datetime import datetime
import logging
from typing import Dict, List, Tuple
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import networkx as nx
from scipy import stats

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('post_processing.log'),
        logging.StreamHandler()
    ]
)

class SimulationAnalyzer:
    def __init__(self, simulation_dir: str):
        self.simulation_dir = Path(simulation_dir)
        self.results_dir = Path('post_processing/results')
        self.configs = ['no_mal_no_int', 'int_no_mal', 'mal_no_int', 'mal_int']
        self.protocols = ['AODV', 'OLSR', 'DSDV', 'DSR']
        self.metrics = {
            'throughput_promedio': 'Kbps',
            'delay_promedio': 'ms',
            'jitter_promedio': 'ms',
            'perdida_paquetes': '%',
            'pdr': '%',
            'paquetes_totales': 'packets',
            'paquetes_perdidos': 'packets',
            'numero_flujos': 'flows',
            'tiempo_simulacion': 's'
        }
        
    def load_metrics(self) -> Dict:
        """Carga todas las métricas de las simulaciones"""
        metrics_data = {}
        for config in self.configs:
            metrics_data[config] = {}
            for protocol in self.protocols:
                metrics_data[config][protocol] = self._load_protocol_metrics(config, protocol)
        return metrics_data

    def _load_protocol_metrics(self, config: str, protocol: str) -> Dict:
        """Carga las métricas para un protocolo específico"""
        protocol_dir = self.simulation_dir / config / protocol
        metrics = {}
        
        for run_dir in protocol_dir.glob('run*'):
            metrics_file = run_dir / 'metrics' / 'metrics.csv'
            if metrics_file.exists():
                try:
                    df = pd.read_csv(metrics_file)
                    metrics[f'run_{run_dir.name}'] = df
                    logging.info(f"Cargado archivo de métricas: {metrics_file}")
                except Exception as e:
                    logging.error(f"Error al cargar {metrics_file}: {str(e)}")
                
        return metrics

    def generate_summary_statistics(self, metrics_data: Dict) -> pd.DataFrame:
        """Genera estadísticas resumen para todas las métricas"""
        summary = []
        
        for config in self.configs:
            for protocol in self.protocols:
                protocol_data = metrics_data[config][protocol]
                for metric, unit in self.metrics.items():
                    values = []
                    for run_data in protocol_data.values():
                        if metric in run_data.columns:
                            values.extend(run_data[metric].values)
                    
                    if values:
                        summary.append({
                            'Configuración': config,
                            'Protocolo': protocol,
                            'Métrica': metric,
                            'Unidad': unit,
                            'Media': np.mean(values),
                            'Mediana': np.median(values),
                            'Std': np.std(values),
                            'Min': np.min(values),
                            'Max': np.max(values)
                        })
        
        return pd.DataFrame(summary)

    def generate_comparative_plots(self, metrics_data: Dict):
        """Genera gráficos comparativos entre protocolos y configuraciones"""
        for metric, unit in self.metrics.items():
            # Gráfico de cajas para comparar protocolos
            self._plot_boxplot(metrics_data, metric, unit)
            
            # Gráfico de líneas para tendencias temporales
            self._plot_temporal_trends(metrics_data, metric, unit)
            
            # Gráfico de calor para correlaciones
            self._plot_correlation_heatmap(metrics_data, metric)

    def _plot_boxplot(self, metrics_data: Dict, metric: str, unit: str):
        """Genera gráfico de cajas para una métrica específica"""
        plt.figure(figsize=(12, 6))
        data = []
        labels = []
        
        for config in self.configs:
            for protocol in self.protocols:
                protocol_data = metrics_data[config][protocol]
                values = []
                for run_data in protocol_data.values():
                    if metric in run_data.columns:
                        values.extend(run_data[metric].values)
                if values:  # Solo agregar si hay datos
                    data.append(values)
                    labels.append(f'{config}\n{protocol}')
        
        if data:  # Solo crear el gráfico si hay datos
            plt.boxplot(data, labels=labels)
            plt.title(f'Distribución de {metric} por Configuración y Protocolo')
            plt.ylabel(f'{metric} ({unit})')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(self.results_dir / 'graphs' / f'{metric}_boxplot.png')
            plt.close()
        else:
            logging.warning(f"No hay datos disponibles para generar el gráfico de cajas de {metric}")

    def _plot_temporal_trends(self, metrics_data: Dict, metric: str, unit: str):
        """Genera gráfico de tendencias temporales"""
        fig = go.Figure()
        
        for config in self.configs:
            for protocol in self.protocols:
                protocol_data = metrics_data[config][protocol]
                for run_name, run_data in protocol_data.items():
                    if metric in run_data.columns:
                        fig.add_trace(go.Scatter(
                            x=run_data.index,
                            y=run_data[metric],
                            name=f'{config} - {protocol} - {run_name}',
                            mode='lines'
                        ))
        
        fig.update_layout(
            title=f'Tendencias Temporales de {metric}',
            xaxis_title='Tiempo',
            yaxis_title=f'{metric} ({unit})',
            showlegend=True
        )
        fig.write_html(self.results_dir / 'graphs' / f'{metric}_temporal.html')

    def _plot_correlation_heatmap(self, metrics_data: Dict, metric: str):
        """Genera mapa de calor de correlaciones"""
        correlation_data = []
        
        for config in self.configs:
            for protocol in self.protocols:
                protocol_data = metrics_data[config][protocol]
                for run_data in protocol_data.values():
                    if all(m in run_data.columns for m in self.metrics.keys()):
                        # Filtrar columnas y reemplazar NaN con 0
                        data = run_data[self.metrics.keys()].fillna(0)
                        # Calcular correlación solo si hay suficientes datos no-NaN
                        if data.notna().sum().min() > 1:  # Al menos 2 valores no-NaN para correlación
                            corr = data.corr()
                            if not corr.isna().all().all():  # Verificar que no todos los valores son NaN
                                correlation_data.append(corr)
        
        if correlation_data:
            # Calcular correlación promedio
            mean_correlation = pd.concat(correlation_data).groupby(level=0).mean()
            
            # Verificar que hay datos válidos para graficar
            if not mean_correlation.isna().all().all():
                plt.figure(figsize=(10, 8))
                sns.heatmap(mean_correlation, annot=True, cmap='coolwarm', center=0, 
                          mask=mean_correlation.isna())  # Enmascarar valores NaN
                plt.title(f'Correlación entre Métricas para {metric}')
                plt.tight_layout()
                plt.savefig(str(self.results_dir / 'graphs' / f'{metric}_correlation.png'))
                plt.close()
            else:
                logging.warning(f"No hay datos válidos para generar el mapa de calor de correlación para {metric}")
        else:
            logging.warning(f"No hay suficientes datos para generar el mapa de calor de correlación para {metric}")

    def generate_report(self, summary_stats: pd.DataFrame):
        """Genera un reporte PDF con los resultados del análisis"""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        
        # Convertir Path a string para el nombre del archivo
        pdf_path = str(self.results_dir / 'reports' / 'analysis_report.pdf')
        
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter
        )
        styles = getSampleStyleSheet()
        elements = []
        
        # Título
        elements.append(Paragraph("Análisis de Simulaciones IoT", styles['Title']))
        elements.append(Spacer(1, 12))
        
        # Resumen ejecutivo
        elements.append(Paragraph("Resumen Ejecutivo", styles['Heading1']))
        elements.append(Paragraph(
            "Este reporte presenta un análisis detallado de las simulaciones de red IoT, "
            "comparando diferentes protocolos de enrutamiento bajo diversas condiciones de red.",
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))
        
        # Tabla de estadísticas
        elements.append(Paragraph("Estadísticas Resumen", styles['Heading1']))
        table_data = [summary_stats.columns.tolist()] + summary_stats.values.tolist()
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        
        # Conclusiones
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Conclusiones", styles['Heading1']))
        elements.append(Paragraph(
            "Basado en el análisis de los datos, se pueden extraer las siguientes conclusiones:",
            styles['Normal']
        ))
        
        # Generar conclusiones automáticamente
        for metric, unit in self.metrics.items():
            metric_data = summary_stats[summary_stats['Métrica'] == metric]
            if not metric_data.empty:
                # Determinar si valores más altos o más bajos son mejores
                is_higher_better = metric in ['throughput_promedio', 'pdr']
                best_idx = metric_data['Media'].idxmax() if is_higher_better else metric_data['Media'].idxmin()
                best_protocol = metric_data.loc[best_idx]
                
                elements.append(Paragraph(
                    f"• Para {metric} ({unit}): El protocolo {best_protocol['Protocolo']} en la configuración "
                    f"{best_protocol['Configuración']} mostró el mejor rendimiento con un valor promedio de "
                    f"{best_protocol['Media']:.2f} {unit}.",
                    styles['Normal']
                ))
        
        # Recomendaciones
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Recomendaciones", styles['Heading1']))
        elements.append(Paragraph(
            "Basado en los resultados del análisis, se recomienda:",
            styles['Normal']
        ))
        
        # Generar recomendaciones automáticamente
        for protocol in self.protocols:
            protocol_data = summary_stats[summary_stats['Protocolo'] == protocol]
            if not protocol_data.empty:
                # Analizar el rendimiento general del protocolo
                throughput_data = protocol_data[protocol_data['Métrica'] == 'throughput_promedio']
                delay_data = protocol_data[protocol_data['Métrica'] == 'delay_promedio']
                pdr_data = protocol_data[protocol_data['Métrica'] == 'pdr']
                
                if not throughput_data.empty and not delay_data.empty and not pdr_data.empty:
                    avg_throughput = throughput_data['Media'].mean()
                    avg_delay = delay_data['Media'].mean()
                    avg_pdr = pdr_data['Media'].mean()
                    
                    elements.append(Paragraph(
                        f"• {protocol}: Este protocolo muestra un rendimiento promedio de {avg_throughput:.2f} Kbps, "
                        f"con una latencia de {avg_delay:.2f} ms y un PDR del {avg_pdr:.2f}%. ",
                        styles['Normal']
                    ))
        
        doc.build(elements)

    def run_analysis(self):
        """Ejecuta todo el proceso de análisis"""
        logging.info("Iniciando análisis de simulaciones...")
        
        # Crear directorios necesarios
        (self.results_dir / 'tables').mkdir(parents=True, exist_ok=True)
        (self.results_dir / 'graphs').mkdir(parents=True, exist_ok=True)
        (self.results_dir / 'reports').mkdir(parents=True, exist_ok=True)
        
        # Cargar datos
        metrics_data = self.load_metrics()
        
        # Generar estadísticas
        summary_stats = self.generate_summary_statistics(metrics_data)
        summary_stats.to_csv(self.results_dir / 'tables' / 'summary_statistics.csv', index=False)
        
        # Generar gráficos
        self.generate_comparative_plots(metrics_data)
        
        # Generar reporte
        self.generate_report(summary_stats)
        
        logging.info("Análisis completado exitosamente")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python run_analysis.py <directorio_simulacion>")
        sys.exit(1)
    
    analyzer = SimulationAnalyzer(sys.argv[1])
    analyzer.run_analysis() 