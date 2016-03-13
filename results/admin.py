from django.contrib import admin

from results.models import ElectionResult, Candidate
from .models import Province, Municipality


class MunicipalityInline(admin.TabularInline):
    model = Municipality
    fields = ['name', 'type']
    show_change_link = True
    extra = 0


class ProvinceAdmin(admin.ModelAdmin):
    list_display = ['name', 'municipalities_no', 'cards_no', 'entitled_no', 'residents_no']
    inlines = [MunicipalityInline]


class ResultInline(admin.TabularInline):
    model = ElectionResult
    extra = 0


class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ['name', 'province', 'valid_votes_no', 'cards_no', 'entitled_no', 'is_fully_filled']
    fields = [('name', 'type'), 'province', ('residents_no', 'entitled_no'), ('cards_no', 'votes_no', 'valid_votes_no')]
    inlines = [ResultInline]


class CandidateAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'votes_no']


admin.site.register(Province, ProvinceAdmin)
admin.site.register(Municipality, MunicipalityAdmin)
admin.site.register(Candidate, CandidateAdmin)