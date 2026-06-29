"""
HTML 报告生成 - 使用 Jinja2 模板渲染
"""
# (C) foxpaw


import time

from flask import render_template


def generate_html_report(all_results, script_name, episode_info=None):
    """生成 HTML 报告"""
    return render_template(
        'report.html',
        script_name=script_name,
        episode_info=episode_info,
        generate_time=time.strftime("%Y-%m-%d %H:%M:%S"),
        results=all_results
    )
