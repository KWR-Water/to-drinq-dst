"""Browse literature removal summaries by chemical identity or treatment."""

import re

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, Prefetch, Q, Value, When
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View

from drinq.models import (
    Citation,
    Compound,
    CompoundCas,
    CompoundRemovalSummary,
    CompoundSynonym,
    Process,
    RemovalDataset,
)

IDENTIFIER_SYNONYM = re.compile(
    r'(?:'
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    r'|[0-9a-f]{16,}'
    r'|[a-z]{14}-[a-z]{10}-[a-z]'
    r'|(?=[a-z0-9]*\d)[a-z0-9]{10}'
    r'|\d[a-z0-9]{3}'
    r'|(?:cid|cas|chebi|chembl|dtxsid|dtxcid|unii|nsc|ncgc|schembl'
    r'|mfcd|akos|hms|tox21)[\s:_-]*[a-z0-9_-]+'
    r')',
    re.IGNORECASE,
)


def is_name_synonym(value: str) -> bool:
    """Exclude recognizable identifiers without rejecting numbered names."""
    name = value.strip()
    return (
        any(character.isalpha() for character in name)
        and not IDENTIFIER_SYNONYM.fullmatch(name)
        and not name.casefold().startswith(
            (
                'inchi=',
                'inchikey=',
                'smiles=',
                'smiles:',
            )
        )
    )


def selection_id(value: str) -> int | None:
    """Return a bounded positive identifier, rejecting malformed input."""
    try:
        identifier = int(value)
    except ValueError:
        return None
    return identifier if 0 < identifier < 2**63 else None


class RemovalRatesView(LoginRequiredMixin, View):
    """Display source summaries without pooling synonyms or study groups."""

    def get(
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse:
        """Search identifiers and display the selected substance or process."""
        mode = request.GET.get('mode', 'substance')
        if mode not in ('substance', 'technology'):
            mode = 'substance'
        search = request.GET.get('q', '').strip()
        suggest = request.GET.get('suggest') == '1'
        if suggest and len(search) > 200:
            return JsonResponse({'error': 'Search is too long.'}, status=400)
        if suggest and len(search) < 2:
            return JsonResponse({'results': [], 'more': False})
        error = ''
        if len(search) > 200:
            search = search[:200]
            error = 'Search is limited to 200 characters.'
        compounds = (
            Compound.objects.filter(
                removal_summaries__isnull=False,
            )
            .distinct()
            .order_by('common_name', 'cid')
        )
        if search and (mode == 'substance' or suggest):
            match = (
                Q(common_name__icontains=search)
                | Q(compoundcas__cas__icontains=search)
                | Q(compoundsynonym__synonym__istartswith=search)
            )
            identifier = selection_id(search)
            if identifier is not None:
                match |= Q(cid=identifier)
            compounds = compounds.filter(match).distinct()
        if suggest:
            matches = list(
                compounds.order_by(
                    Case(
                        When(common_name__istartswith=search, then=Value(0)),
                        default=Value(1),
                    ),
                    'common_name',
                    'cid',
                )[:16]
            )
            visible_matches = matches[:15]
            cas_by_cid: dict[int, list[str]] = {}
            for cid, cas in (
                CompoundCas.objects.filter(
                    cid_id__in=[compound.pk for compound in visible_matches],
                )
                .exclude(cas__isnull=True)
                .exclude(cas='')
                .order_by(
                    'cas',
                )
                .values_list('cid_id', 'cas')
            ):
                cas_by_cid.setdefault(cid, []).append(cas)
            return JsonResponse(
                {
                    'results': [
                        {
                            'cid': compound.pk,
                            'name': compound.common_name
                            or 'Unnamed substance',
                            'cas_numbers': cas_by_cid.get(compound.pk, []),
                        }
                        for compound in visible_matches
                    ],
                    'more': len(matches) > 15,
                }
            )
        processes = (
            Process.objects.filter(
                removal_summaries__isnull=False,
            )
            .distinct()
            .order_by('description', 'name')
        )
        selected_compound = None
        selected_process = None
        summaries = CompoundRemovalSummary.objects.none()
        cas_numbers: list[str] = []
        synonyms: list[str] = []
        more_synonyms = False
        if mode == 'substance':
            raw_id = request.GET.get('compound', '')
            identifier = selection_id(raw_id)
            if identifier is not None:
                selected_compound = compounds.filter(pk=identifier).first()
            elif search and not raw_id and compounds.count() == 1:
                selected_compound = compounds.first()
            if raw_id and selected_compound is None:
                error = 'The selected substance is not available.'
            if selected_compound is not None:
                summaries = CompoundRemovalSummary.objects.filter(
                    compound=selected_compound,
                )
                cas_numbers = list(
                    CompoundCas.objects.filter(
                        cid=selected_compound,
                    )
                    .exclude(cas__isnull=True)
                    .exclude(cas='')
                    .order_by('cas')
                    .values_list('cas', flat=True)
                )
                synonym_candidates: list[str] = []
                seen_synonyms = {
                    (selected_compound.common_name or '').strip().casefold()
                }
                for candidate in (
                    CompoundSynonym.objects.filter(cid=selected_compound)
                    .exclude(synonym__isnull=True)
                    .exclude(synonym='')
                    .exclude(
                        synonym__iexact=selected_compound.common_name or '',
                    )
                    .order_by('synonym')
                    .values_list('synonym', flat=True)
                    .distinct()
                    .iterator()
                ):
                    name = candidate.strip()
                    normalized = name.casefold()
                    if normalized in seen_synonyms or not is_name_synonym(
                        name
                    ):
                        continue
                    seen_synonyms.add(normalized)
                    synonym_candidates.append(name)
                    if len(synonym_candidates) == 6:
                        break
                synonyms = synonym_candidates[:5]
                more_synonyms = len(synonym_candidates) > 5
        else:
            raw_id = request.GET.get('process', '')
            identifier = selection_id(raw_id)
            if identifier is not None:
                selected_process = processes.filter(pk=identifier).first()
            if raw_id and selected_process is None:
                error = 'The selected technology is not available.'
            if selected_process is not None:
                summaries = CompoundRemovalSummary.objects.filter(
                    process=selected_process,
                )
        results = list(
            summaries.select_related(
                'compound',
                'process',
                'dataset',
                'dataset__publication',
            )
            .prefetch_related(
                Prefetch(
                    'dataset__sources',
                    queryset=Citation.objects.order_by('key'),
                )
            )
            .order_by(
                'process__description'
                if mode == 'substance'
                else 'compound__common_name',
                'compound__cid',
                'dataset__key',
                'source_row_number',
            )
        )
        datasets: dict[int, RemovalDataset] = {
            row.dataset.pk: row.dataset for row in results
        }
        return render(
            request,
            'drinq/removal_rates.html',
            {
                'mode': mode,
                'search': search,
                'compounds': compounds,
                'processes': processes,
                'selected_compound': selected_compound,
                'selected_process': selected_process,
                'cas_numbers': cas_numbers,
                'synonyms': synonyms,
                'more_synonyms': more_synonyms,
                'summaries': results,
                'datasets': list(datasets.values()),
                'selection_error': error,
                'identity_review_cids': (25210, 119411),
            },
        )
