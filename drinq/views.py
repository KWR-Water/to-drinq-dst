from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, HttpResponseRedirect, QueryDict
from django.views import generic
from drinq.models import (
    Compound, CompoundCas, Configuration, Technology, Process, DesignTree,
)
from drinq.forms import TechnologyForm, DecidingFactor
from drinq.chemistry_tools import smiles_to_svg
import drinq.decision_tree as dst

EXCLUDE_KEY = ['csrfmiddlewaretoken', 'next']


def process_form_data(
    post_request: QueryDict,
) -> dict[str, str]:
    querydata = {}
    for key, value in post_request.items():
        if key in EXCLUDE_KEY:
            continue
        if isinstance(value, str):
            if value == 'on':
                querydata[key] = True
    return querydata


class Register(generic.TemplateView):
    template_name = "drinq/register.html"


class Welcome(generic.TemplateView):
    template_name = "drinq/welcome.html"


class PasswordChangeOk(generic.TemplateView):
    template_name = "drinq/password_change_ok.html"


def index(request: HttpResponse):
    """Displays the index HTML page (index.html).

    Args:
        request (HttpResponse): http response object

    Returns:
        _type_: _description_
    """

    # return HttpResponse("Hello, world. You're at the drinq index.")
    return render(request, 'drinq/index.html')


def db_stats(request: HttpResponse):
    """Puts database statistics in a dictionary. The corresponding HTML
    template is `db_stats.html`.

    Args:
        request (HttpResponse): http response object.

    Returns:
        Dict[str, Any]: dictionary with database statistics (counts, etc.)
    """
    num_compounds = Compound.objects.all().count()
    num_technologies = Technology.objects.all().count()

    context = {
        'num_compounds': num_compounds,
        'num_technologies': num_technologies,
    }
    return render(request, 'drinq/db_stats.html', context=context)


def dst_form_surfacewater(request: HttpResponse):
    # if this is a POST request we need to process the form data
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        # old code --> manual checkboxes:
        querydata = process_form_data(post_request=request.POST)
        # surface_water_id = DesignTree.objects.get(name='surface_water').id
        # ground_water_id = DesignTree.objects.get(name='ground_water').id
            
        form = TechnologyForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            if 'source_is_surface_water' in form.changed_data:
                df_sw = DecidingFactor.objects.get(
                    name='source_is_surface_water')
                selected = dst.decision_stage_screening(
                    decidingfactor_parent=df_sw, form_data=form.cleaned_data)
            # form.save()
            # render the result in a new URL:
            return render(request, 'drinq/form_result.html', context=selected)
        else:
            return HttpResponseRedirect(redirect('drinq_redirect'))
    # if a GET (or any other method) we'll create a blank form
    else:
        form = TechnologyForm()
        return render(request, "drinq/form.html", {"form": form})


def compound_search(request: HttpResponse):
    pass


def compound_detail(request, cid):
    try:
        compound = Compound.objects.get(cid=cid)
    except Compound.DoesNotExist:
        raise Http404("Compound does not exist")
    try:
        cas_list = CompoundCas.objects.filter(cid=cid)
    except CompoundCas.DoesNotExist:
        cas_list = None

    svg_compound = smiles_to_svg(smiles=compound.isomeric_smiles)

    context = {'cid': compound.cid,
               'common_name': compound.common_name,
               'isomeric_smiles': compound.isomeric_smiles,
               'cas_list': cas_list,
               'svg_image': svg_compound,
               }
    return render(request, 'drinq/compound/detail.html', context)
