from random import randrange

from flask import Flask,request,render_template_string
from jinja2 import Markup, Environment, FileSystemLoader
from pyecharts import options as opts
from pyecharts.charts import Kline, Line, Bar, Grid
from pyecharts.globals import ThemeType
import pandas as pd
import requests

app = Flask(__name__, static_folder="templates")


def bar_base() -> Bar:
    c = (
        Bar()
        .add_xaxis(["衬衫", "羊毛衫", "雪纺衫", "裤子", "高跟鞋", "袜子"])
        .add_yaxis("商家A", [randrange(0, 100) for _ in range(6)])
        .add_yaxis("商家B", [randrange(0, 100) for _ in range(6)])
        .set_global_opts(title_opts=opts.TitleOpts(title="Bar-基本示例", subtitle="我是副标题"))
    )
    return c

def kline_base(code,period,start_time,end_time):
    req_str = 'http://10.42.7.40:10411/query/futureKline?'
    #将入参拼接到url中
    req_str = req_str + '&code=' + code + '&period=' + period + '&start_time=' + start_time + '&end_time=' + end_time
    response = requests.get(req_str)

    # 解析返回的JSON数据
    data = response.json()
    # print(data)
    # json 转data frame

    df_data = pd.DataFrame(data)

    df_data['bar_time'] = pd.to_datetime(df_data['bar_time'], format ='%Y%m%d%H%M%S')

    df_data['bar_time'] = df_data['bar_time'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S'))
    print(df_data)
    #将df_data 中 开高低收转成list
    data_list = df_data[['open','close','low','high']].values.tolist()

    c = (
        Kline()
        .add_xaxis(xaxis_data=df_data["bar_time"].to_list())
        .add_yaxis(
            series_name="Dow-Jones index",
            y_axis=data_list,
            itemstyle_opts=opts.ItemStyleOpts(color="#ec0000", color0="#00da3c"),
        )
        .set_global_opts(
            legend_opts=opts.LegendOpts(
                is_show=False, pos_bottom=10, pos_left="center"
            ),
            datazoom_opts=[
                opts.DataZoomOpts(
                    is_show=False,
                    type_="inside",
                    xaxis_index=[0, 1],
                    range_start=98,
                    range_end=100,
                ),
                opts.DataZoomOpts(
                    is_show=True,
                    xaxis_index=[0, 1],
                    type_="slider",
                    pos_top="85%",
                    range_start=98,
                    range_end=100,
                ),
            ],
            yaxis_opts=opts.AxisOpts(
                is_scale=True,
                splitarea_opts=opts.SplitAreaOpts(
                    is_show=True, areastyle_opts=opts.AreaStyleOpts(opacity=1)
                ),
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="cross",
                background_color="rgba(245, 245, 245, 0.8)",
                border_width=1,
                border_color="#ccc",
                textstyle_opts=opts.TextStyleOpts(color="#000"),
            ),
            visualmap_opts=opts.VisualMapOpts(
                is_show=False,
                dimension=2,
                series_index=5,
                is_piecewise=True,
                pieces=[
                    {"value": 1, "color": "#00da3c"},
                    {"value": -1, "color": "#ec0000"},
                ],
            ),
            axispointer_opts=opts.AxisPointerOpts(
                is_show=True,
                link=[{"xAxisIndex": "all"}],
                label=opts.LabelOpts(background_color="#777"),
            ),
            brush_opts=opts.BrushOpts(
                x_axis_index="all",
                brush_link="all",
                out_of_brush={"colorAlpha": 0.1},
                brush_type="lineX",
            ),
        )
    )
    bar = (
                Bar()
                .add_xaxis(xaxis_data=df_data['bar_time'].tolist())
                .add_yaxis(
                    series_name="volume",
                    y_axis=df_data["volume"].to_list(),
                    xaxis_index=1,
                    yaxis_index=1,
                    label_opts=opts.LabelOpts(is_show=False),
                )
                .set_global_opts(
                xaxis_opts=

        opts.AxisOpts(
                    type_="category",
                    is_scale=True,
                    grid_index=1,
                    boundary_gap=False,
                    axisline_opts=opts.AxisLineOpts(is_on_zero=False),
                    axistick_opts=opts.AxisTickOpts(is_show=False),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                    axislabel_opts=opts.LabelOpts(is_show=False),
                    split_number=20,
                    min_="dataMin",
                    max_="dataMax",
                ),
                yaxis_opts=opts.AxisOpts(
                    grid_index=1,
                    is_scale=True,
                    split_number=2,
                    axislabel_opts=opts.LabelOpts(is_show=False),
                    axisline_opts=opts.AxisLineOpts(is_show=False),
                    axistick_opts=opts.AxisTickOpts(is_show=False),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                ),
                legend_opts=opts.LegendOpts(is_show=False),
            )
        )
    grid_chart = Grid(
        init_opts=opts.InitOpts(
            width="1000px",
            height="800px",
            animation_opts=opts.AnimationOpts(animation=False),
        )
    )
    grid_chart.add(
        c,
        grid_opts=opts.GridOpts(pos_left="10%", pos_right="8%", height="50%"),
    )
    grid_chart.add(
        bar,
        grid_opts=opts.GridOpts(
            pos_left="10%", pos_right="8%", pos_top="63%", height="16%"
        ),
    )


    return grid_chart


# @app.route("/")
# def get_kline_chart():
#     c = kline_base()
#     return Markup(c.render_embed())

@app.route("/", methods=["GET", "POST"])
def home():
    # 如果是POST请求，获取用户输入
    if request.method == "POST":
        code = request.form["code"]
        period = request.form["period"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        # 处理用户输入
        c = kline_base(code, period, start_time, end_time);
        return Markup(c.render_embed())
    else:
        # kline_chart_html = kline_base().render_notebook()
        # 渲染K线图表和表单
        return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
            </head>
            <body>
                <form method="post">
                    <input type="text" name="code">
                    <input type="text" name="period">
                    <input type="text" name="start_time">
                    <input type="text" name="end_time">
                    <input type="submit" value="Submit">
                </form>
            </body>
            </html>
        """)

if __name__ == "__main__":
    app.run()