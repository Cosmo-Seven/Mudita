from models.site_models import SiteModel


def site(request):
    site = SiteModel.objects.first()
    return {"site": site}
