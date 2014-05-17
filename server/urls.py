from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

import views
import manager.hooks

urlpatterns = patterns('',
    (r'^$', views.index),
    (r'^api/configure/$', views.configure),
    (r'^api/data/((?P<start>\d+)/)?$', views.list_values),
    (r'^api/data/daily/((?P<start>\d+)/)?$', views.list_values, {'accuracy': 'day'}),
    (r'^api/forecast/$', views.forecast),
    (r'^api/live/$', views.live_data),
    (r'^api/login/$', views.login_user),
    (r'^api/logout/$', views.logout_user),
    (r'^api/manage/thresholds/$', views.handle_threshold),
    (r'^api/notifications/$', views.list_notifications),
    (r'^api/sensors/$', views.list_sensors),
    (r'^api/settings/$', views.settings),
    (r'^api/start/$', views.start_system),
    (r'^api/statistics/(start/(?P<start>\d+)/)?(end/(?P<end>\d+)/)?$', views.get_statistics),
    (r'^api/statistics/monthly/(start/(?P<start>\d+)/)?(end/(?P<end>\d+)/)?$', views.get_monthly_statistics),
    (r'^api/status/$', views.status),
    (r'^api/thresholds/$', views.list_thresholds),

    (r'^api2/balance/totals/$', manager.hooks.get_totals),
    (r'^api2/balance/infeed/$', manager.hooks.get_infeed),
    (r'^api2/balance/purchase/$', manager.hooks.get_purchase),
    (r'^api2/balance/maintenance/$', manager.hooks.get_maintenance_costs),
    (r'^api2/consumption/thermal/$', manager.hooks.get_thermal_consumption),
    (r'^api2/consumption/warmwater/$', manager.hooks.get_warmwater_consumption),
    (r'^api2/consumption/electrical/$', manager.hooks.get_electrical_consumption),
    (r'^api2/consumption/cu/$', manager.hooks.get_cu_consumption,),
    (r'^api2/consumption/plb/$', manager.hooks.get_plb_consumption),
    (r'^api2/sums/((?P<sensor_id>\d+)/)?$', manager.hooks.get_sums),

    url(r'^admin/', include(admin.site.urls)),
)
