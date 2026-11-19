"""Plotly timelines with explicit UTC date coordinates (no epoch integer x-axis shapes).

This module is UI-independent, enabling regression tests without Streamlit.
"""
from __future__ import annotations
import pandas as pd
import plotly.graph_objects as go


def utc_time(value) -> pd.Timestamp:
    """Preserve absolute instants; all timeline axes use timezone-aware UTC."""
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError('Invalid event timestamp')
    return ts.tz_localize('UTC') if ts.tzinfo is None else ts.tz_convert('UTC')


def event_plot(g: pd.DataFrame, start=None, minutes: int = 5) -> go.Figure:
    if minutes <= 0:
        raise ValueError('minutes must be positive')
    data = g.copy()
    data['timestamp'] = pd.to_datetime(data['timestamp'], utc=True)
    event_time = utc_time(start) if start is not None else None
    if event_time is not None:
        lo = event_time - pd.Timedelta(minutes=minutes)
        hi = event_time + pd.Timedelta(minutes=minutes)
        data = data.loc[data['timestamp'].between(lo, hi)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.timestamp.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), y=data.flow_lpm, name='Flow (L/min)',
                             mode='lines+markers', line=dict(color='#16a0a7', width=2),
                             marker=dict(size=4)))
    if 'status' in data.columns:
        points = data.loc[data.status.isin(['WATCH', 'ALERT'])]
        if not points.empty:
            fig.add_trace(go.Scatter(x=points.timestamp.dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), y=points.flow_lpm,
                                     name='Flagged', mode='markers',
                                     marker=dict(size=10, color=['#da605a' if x == 'ALERT' else '#dbab40'
                                                                 for x in points.status])))
    if event_time is not None:
        # DATE string, not a millisecond integer: prevents Plotly's malformed event axis.
        x_event = event_time.isoformat()
        fig.add_shape(type='line', xref='x', yref='paper', x0=x_event, x1=x_event,
                      y0=0, y1=1, line=dict(color='#ce963b', width=2, dash='dash'))
        fig.update_xaxes(type='date', range=[lo.isoformat(), hi.isoformat()],
                         tickformat='%H:%M:%S')
    fig.update_layout(height=330, margin=dict(t=20, b=10, l=18, r=15),
                      xaxis_title='Time (UTC)', yaxis_title='Flow (L/min)',
                      legend=dict(orientation='h'))
    return fig
