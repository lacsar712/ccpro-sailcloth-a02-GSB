from django.contrib import admin

from .models import ClothRoll, DipRun, Loft, StretcherTag


@admin.register(StretcherTag)
class StretcherTagAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "stretcher_no",
        "roll",
        "holder",
        "checked_out_at",
        "returned_at",
    )
    list_filter = ("returned_at", "stretcher_no")
    search_fields = ("roll__roll_code", "holder__username")


admin.site.register(Loft)
admin.site.register(ClothRoll)
admin.site.register(DipRun)
