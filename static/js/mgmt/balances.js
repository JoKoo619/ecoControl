var diagram_types = ['balances', 'rewards', 'costs'];
var month_list = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
var cached_data = {};

// READY
$(function() {
    initialize_diagram();
    initialize_diagram_filters();

    // resize charts in tabs
    $.each(diagram_types, function(index, type) {
        var container = $('#' + type + '_container');
        var chart = container.highcharts();
        chart.setSize(container.parent().width(), container.parent().height(), false);
    });
});

function initialize_diagram() {
    $.each(diagram_types, function(index, type) {
        $('#' + type + '_container').highcharts({
            chart: {
                zoomType: 'xy'
            },
            title: {
                text: ''
            },
            xAxis: {
                categories: month_list
            },
            yAxis: [{
                labels: {
                    format: '{value} €',
                    style: { color: Highcharts.getOptions().colors[1] }
                },
                title: {
                    text: 'Balances in €',
                    style: { color: Highcharts.getOptions().colors[1] }
                },
            }],
            plotOptions: {
                series: {
                    cursor: 'pointer',
                    point: {
                        events: {
                            click: function (e) {
                                var month = month_list.indexOf(e.currentTarget.category);
                                var year = get_year_from_string(this.series.name);
                                show_month_details(year, month);
                            }
                        }
                    },
                    marker: {
                        lineWidth: 1
                    }
                }
            },
            tooltip: {
                valueDecimals: 2
            },
            series: [],
            credits: {
                enabled: false
            }
        });
    });
}

function initialize_diagram_filters() {
    $.getJSON('/api2/history/', function(history_data) {
        $.each(history_data, function(index, year) {
            $('#diagram_filters').append(
                '<label class="btn btn-default">\
                <input class="btn diagram_filter" type="checkbox" value="' + year + '">\
                ' + year + '</label>');
        });
        $('.diagram_filter').change(function () {

            charts = [];
            $.each(diagram_types, function(index, type) {
                charts.push($('#' + type + '_container').highcharts());
            });
            var year = parseInt($(this).val());
            if ($(this).is(":checked")) {
                var found = false;
                $.each(charts, function(index, chart) {
                    $.each(chart.series, function(index2, series) {
                        if (series['name'].substr(series['name'].length - 4) == year) {
                            series.show(false);
                            found = true;
                        }
                    });
                });
                if (!found) {
                    $.getJSON("/api2/balance/total/" + year + "/", function(data) {
                        cached_data[year] = data;
                        var balances = {
                            name: 'Total Balances in ' + year,
                            type: 'column',
                            data: []
                        };
                        var rewards = {
                            name: 'Total Rewards in ' + year,
                            type: 'column',
                            data: []
                        };
                        var costs = {
                            name: 'Total Costs in ' + year,
                            type: 'column',
                            data: [],
                        };
                        $.each(data, function(index, monthly_data) {
                            balances['data'].push(monthly_data.balance);
                            rewards['data'].push(monthly_data.rewards);
                            costs['data'].push(monthly_data.costs);
                        });
                        charts[0].addSeries(balances);
                        charts[1].addSeries(rewards);
                        charts[2].addSeries(costs);

                        // preselect tables details
                        if ($('#details_container').is(':empty')) {
                            show_month_details(year, data.length - 1);
                        }
                    });
                }
            } else {
                $.each(charts, function(index, chart) {
                    $.each(chart.series, function(index, series) {
                        if (get_year_from_string(series['name']) == year) {
                            series.hide(false);
                        }
                    });
                });
            }

            // if all series are unchecked, show all
            var all_unchecked = true;
            $(".diagram_filter").each(function() {
                if ($(this).is(":checked")) {
                    all_unchecked = false;
                }
            });
            if (all_unchecked) {
                $.each(charts, function(index, chart) {
                    $.each(chart.series, function(index, series) {
                        series.setVisible(true, false);
                    });
                });
            }

            // finally redraw all charts
            $.each(charts, function(index, chart) {
                chart.redraw();
            });
        });

        // preselect first filter
        $('.diagram_filter').first().parent().button('toggle');
    });
}

function show_month_details(year, month) {
    $.each(cached_data[year], function(index, monthly_data) {
        if (month == index) {
            update_table(monthly_data, year, month);
        }
    });
}

function update_table(data, year, month) {
    var container = $('#details_container');
    container.html(
        '<div class="page-header">\
          <h1>' + $.format.date(new Date(year, month, 1), "MMMM yyyy") + '</h1>\
        </div>\
        <table class="table table-striped">\
          <thead>\
            <tr>\
              <th></th>\
              <th>Description</th>\
              <th>Price per Unit</th>\
              <th>Amount</th>\
              <th>Price</th>\
            </tr>\
          </thead>\
          <tbody>\
            <tr>\
              <td rowspan="4" class="text-center" style="vertical-align: middle;"><b>Revenues</b><br>' + data['rewards'] + ' €</td>\
              <td style="padding-left: 20px">' + get_text('thermal_consumption') + '</td>\
              <td>' + data['prices']['thermal_revenues'] + ' €</td>\
              <td>' + data['kwh']['thermal_consumption'] + ' kWh</td>\
              <td>' + Math.round(data['kwh']['thermal_consumption'] * data['prices']['thermal_revenues'] * 100)/100 + ' €</td>\
            </tr>\
            <tr>\
              <td style="padding-left: 20px">' + get_text('warmwater_consumption') + '</td>\
              <td>' + data['prices']['warmwater_revenues'] + ' €</td>\
              <td>' + data['kwh']['warmwater_consumption'] + ' kWh</td>\
              <td>' + Math.round(data['kwh']['warmwater_consumption'] * data['prices']['warmwater_revenues'] * 100)/100 + ' €</td>\
            </tr>\
            <tr>\
              <td style="padding-left: 20px">' + get_text('electrical_consumption') + '</td>\
              <td>' + data['prices']['electrical_revenues'] + ' €</td>\
              <td>' + data['kwh']['electrical_consumption'] + ' kWh</td>\
              <td>' + Math.round(data['kwh']['electrical_consumption'] * data['prices']['electrical_revenues'] * 100)/100 + ' €</td>\
            </tr>\
            <tr>\
              <td style="padding-left: 20px">' + get_text('electrical_infeed') + '</td>\
              <td>' + data['prices']['feed_in_reward'] + ' €</td>\
              <td>' + data['kwh']['electrical_infeed'] + ' kWh</td>\
              <td>' + Math.round(data['kwh']['electrical_infeed'] * data['prices']['feed_in_reward'] * 100)/100 + ' €</td>\
            </tr>\
            <tr>\
              <td rowspan="2" class="text-center" style="vertical-align: middle;"><b>Costs</b><br>' + data['costs'] + ' €</td>\
              <td style="padding-left: 20px">' + get_text('gas_consumption') + '</td>\
              <td>' + data['prices']['gas_costs'] + ' €</td>\
              <td>' + data['kwh']['gas_consumption'] + ' kWh</td>\
              <td>' + Math.round(data['kwh']['gas_consumption'] * data['prices']['gas_costs'] * 100)/100 + ' €</td>\
            </tr>\
            <tr>\
              <td style="padding-left: 20px">' + get_text('electrical_purchase') + '</td>\
              <td>' + data['prices']['electrical_costs'] + ' €</td>\
              <td>' + data['kwh']['electrical_purchase'] + ' kWh</td>\
              <td>' + Math.round(data['kwh']['electrical_purchase'] * data['prices']['electrical_costs'] * 100)/100 + ' €</td>\
            </tr>\
            <tr>\
              <td colspan="5"></td>\
            </tr>\
            <tr>\
              <td></td>\
              <td></td>\
              <td></td>\
              <td><b>' + get_text('total_balance') + '</b></td>\
              <td><b>' + data['balance'] + ' €</b></td>\
            </tr>\
          </tbody>\
        </table>'
    );
}

function get_year_from_string(string) {
    return string.substr(string.length - 4);
}
