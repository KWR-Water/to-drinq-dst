from django.shortcuts import render
from django.http import HttpResponse, Http404
from drinq.models import Compound, CompoundCas
from drinq.chemistry_tools import smiles_to_svg

def index(request):
    return HttpResponse("Hello, world. You're at the drinq index.")


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
