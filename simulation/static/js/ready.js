var devices_info = null;
var series_data = [];

$(function(){
    $.get( "/static/img/simulation.svg", function( data ) {
        var svg_item = document.importNode(data.documentElement,true);
        $("#simulation_scheme").append(svg_item);
    }, "xml");

    $.getJSON( "/api/info/", function( info ) {
        devices_info = info;
        $.each(info, function(device_id, device_data) {
            $.each(device_data, function(sensor_name, unit){
                if(["name", "energy_external", "energy_infeed"].indexOf(sensor_name) == -1){
                    series_data.push({
                        name: device_data['name'] + " " + sensor_name,
                        data: [],
                        tooltip: {
                            valueSuffix: ' ' + unit
                        }
                    });
                }
            });
        });
    }).done(function(){
        $.getJSON( "/api/data/", function( data ) {
            var i = 0;
            var timestamp = (new Date()).getTime();
            $.each(data, function(device_id, device_data) {
                $.each(device_data, function(sensor_name, value){
                    if(["name", "energy_external", "energy_infeed"].indexOf(sensor_name) == -1){
                        series_data[i]['data'].push([timestamp, parseFloat(value)]);
                        i++;
                    }
                });
            });
        }).done(function(){
            initialize_diagram();
            setInterval(function(){
                refresh()
            }, 500);
        });
    });

    initialize_buttons();
});

function refresh(){
    $.getJSON( "/api/data/", function( data ) {
        update_scheme(data);
        update_diagram(data);
    });
}

function update_scheme(data){
    $.each(data, function(device_id, device_data) {
        var namespace = get_namespace_for_id(device_id);
        $.each(device_data, function(key, value){
            var item = $('#' + namespace + "_" + key);
            if (item.length) {
                item.text(Math.floor(parseFloat(value)*1000)/1000 + " " + devices_info[device_id][key]);
            }
        });
    });
}

function get_namespace_for_id(id){
    switch(id){
        case "0":
            return "bhkw";
        case "1":
            return "hs";
        case "2":
            return "rad1";
        case "3":
            return "elec";
        case "4":
            return "plb";
        case "5":
            return "rad2";
        case "6":
            return "rad3";
    }
}

function update_diagram(data){
    var chart = $('#simulation_diagram').highcharts();
    var i = 0;
    var timestamp = (new Date()).getTime();
    $.each(data, function(device_id, device_data) {
        $.each(device_data, function(sensor_name, value){
            if(["name", "energy_external", "energy_infeed"].indexOf(sensor_name) == -1){
                chart.series[i].addPoint([timestamp, parseFloat(value)], false);
                i++;
            }
        });
    });
    chart.redraw();
}

function initialize_buttons(){
    $("#form_consumption").submit(function(){
        $.post( "/api/set/", { electric_consumption: $("#electric_consumption").val() }).done(function(){
            $("#consumption_button").removeClass("btn-primary").addClass("btn-success");
            setTimeout(function(){
                $("#consumption_button").removeClass("btn-success").addClass("btn-primary");
            },1000);
        });
        event.preventDefault();
    });

    $("#form_temperature").submit(function(){
        $.post( "/api/set/", { room_temperature: $("#room_temperature").val() }).done(function(){
            $("#temperature_button").removeClass("btn-primary").addClass("btn-success");
            setTimeout(function(){
                $("#temperature_button").removeClass("btn-success").addClass("btn-primary");
            },1000);
        });
        event.preventDefault();
    });
}

function initialize_diagram(){
    Highcharts.setOptions({
        global : {
            useUTC : false
        }
    });
    
    // Create the chart
    $('#simulation_diagram').highcharts('StockChart', {
        rangeSelector: {
            buttons: [{
                count: 1,
                type: 'minute',
                text: '1M'
            }, {
                count: 5,
                type: 'minute',
                text: '5M'
            }, {
                count: 10,
                type: 'minute',
                text: '10M'
            }, {
                count: 1,
                type: 'hour',
                text: '1H'
            }, {
                count: 12,
                type: 'hour',
                text: '12H'
            }, {
                count: 1,
                type: 'day',
                text: '1D'
            }, {
                count: 7,
                type: 'day',
                text: '7D'
            }, {
                type: 'all',
                text: 'All'
            }],
            selected: 0
        },
        
        title : {
            text : 'Live simulation data'
        },

        yAxis: {
            min: 0
        },
        
        tooltip : {
            valueDecimals : 2
        },

        plotOptions: {
            series: {
                marker: {
                    enabled: false
                },
                lineWidth: 1,
            }
        },
        
        series : series_data,

        credits: {
            enabled: false
        }
    });
}