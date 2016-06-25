from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.exceptions import SuspiciousOperation
from django.db.models.aggregates import Sum
from django.db.models.functions import Coalesce
from django.db.models.query_utils import Q
from django.http.response import JsonResponse
from django.shortcuts import render

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView

from results.models import Municipality, Province, Candidate, ElectionResult
from results.serializers import ProvinceSerializer, MunicipalitySerializer, CandidateSerializer, \
    ElectionResultsSerializer


def color_conf(statistics, min_value=50, max_value=100, full_value=100):
    ctx = dict()

    color_unknown = 'lightgray'
    color_indecisive = '#BEFFA7'
    color_scale = [
        (50, ['#cce3ff', '#ffdb70']),
        (55, ['#b4d5fd', '#ffcd70']),
        (60, ['#99c7ff', '#ffc15e']),
        (65, ['#7db7fe', '#ffb554']),
        (70, ['#5aa4fe', '#ffa951']),
        (75, ['#3590ff', '#ff9d39']),
        (80, ['#0273fd', '#fe9020']),
        (85, ['#0260d4', '#ff8609']),
        (90, ['#014aa3', '#e77900']),
        (95, ['#003575', '#ce6800']),
    ]
    colors = ['#0260d4', '#ff8609']
    ctx['color_unknown'] = color_unknown
    ctx['color_indecisive'] = color_indecisive
    ctx['color_scale'] = color_scale
    ctx['colors'] = colors

    candidates = statistics['candidates']
    candidate_colors = {candidates[i].id: i if i < len(colors) else -1 for i in range(len(candidates))}

    class Colorizer:
        @staticmethod
        def color(candidate_id):
            if candidate_colors[candidate_id] == -1:
                return color_unknown
            else:
                return colors[candidate_colors[candidate_id]]

        @staticmethod
        def scaled_color(candidate_id, value, full):
            if candidate_colors[candidate_id] == -1:
                return color_unknown
            elif value*full_value < min_value*full or (value == 0 and full == 0 and min_value > 0):
                return color_unknown
            elif value*full_value == min_value*full:
                return color_indecisive
            else:
                value_idx = -1
                for ce in color_scale:
                    if value*full_value >= ce[0]*full:
                        value_idx += 1
                    else:
                        break
                if value_idx == -1:
                    return color_unknown
                else:
                    return color_scale[value_idx][1][candidate_colors[candidate_id]]

        @staticmethod
        def get_unknown_color():
            return color_unknown

        @staticmethod
        def get_indecisive_color():
            return color_indecisive

        @staticmethod
        def get_scale():
            """
            Returns array containing scale - please do not modify it!
            :return: An array containing scale.
            """
            return color_scale

    return Colorizer()


def map_window(request, statistics):
    ctx = dict()
    ctx['map_colors'] = dict()

    ctx['color_scale'] = statistics['colorizer'].get_scale()
    ctx['color_unknown'] = statistics['colorizer'].get_unknown_color()
    ctx['color_indecisive'] = statistics['colorizer'].get_indecisive_color()
    return ctx


def index(request):
    stats = dict()
    ctx = dict()

    candidates = list(Candidate.objects.all())
    stats['candidates'] = candidates

    if len(candidates) != 2:
        print("CANDS")
        raise SuspiciousOperation(
            'Website admins are not good enough to provide valid voting results - there is third candidate.'
        )

    colorizer = color_conf(stats)
    stats['colorizer'] = colorizer

    ctx['candidates'] = candidates

    ctx['map_window'] = map_window(request, stats)
    ctx['candidates'] = stats['candidates']

    return render(request, 'results/compare.html', ctx)


def global_stats(requests):
    ctx = dict()
    stats = dict()

    candidates = list(Candidate.objects.all())
    stats['candidates'] = candidates

    lft = candidates[0].id
    rgt = candidates[1].id

    if len(candidates) != 2:
        raise SuspiciousOperation(
            'Website admins are not good enough to provide valid voting results - there is third candidate.'
        )

    def aggregate_votings(municipality_filter, result_filter):
        result = {'voting': Municipality.objects.filter(municipality_filter).aggregate(residents=Coalesce(Sum('residents_no'), 0),
                                                                                       entitled=Coalesce(Sum('entitled_no'), 0),
                                                                                       cards=Coalesce(Sum('cards_no'), 0),
                                                                                       votes=Coalesce(Sum('votes_no'), 0),
                                                                                       valid_votes=Coalesce(Sum('valid_votes_no'), 0)),
                  'results': {c.id: c.results.filter(result_filter).aggregate(sum=Coalesce(Sum('votes'), 0))['sum']
                              for c in Candidate.objects.all()}}
        result['voting']['sum'] = sum(filter(None, result['results'].values()))
        return result

    stats['global'] = aggregate_votings(Q(), Q())

    poland_municipality_filter = Q(type=Municipality.Type.City) | Q(type=Municipality.Type.Village)
    poland_result_filter = Q(municipality__type=Municipality.Type.City) | Q(municipality__type=Municipality.Type.Village)

    stats['poland'] = aggregate_votings(poland_municipality_filter, poland_result_filter)

    ctx['residents'] = stats['poland']['voting']['residents']
    ctx['entitled'] = stats['poland']['voting']['entitled']
    ctx['cards'] = stats['poland']['voting']['cards']
    ctx['votes'] = stats['poland']['voting']['votes']
    ctx['valid_votes'] = stats['poland']['voting']['valid_votes']
    ctx['votes_a'] = stats['global']['results'][lft]
    ctx['votes_b'] = stats['global']['results'][rgt]
    ctx['votes_s'] = stats['global']['voting']['sum']

    return JsonResponse(ctx)

def edit_results(request):
    if request.user.is_anonymous():
        raise SuspiciousOperation("Login required")
    if request.method == "POST":
        data = request.POST

        # find municipality
        m = Municipality.objects.get(id=data['id'])
        if not m:
            raise SuspiciousOperation("Municipality do not exist!")

        if m.update_token != data['update_token']:
            return JsonResponse({'result': 'modified-in-the-meantime',
                                 'update_user': m.update_user.username if m.update_user else 'unknown',
                                 'update_time': str(m.update_time)
                                 })
        else:
            def iot(x):
                if x == '': return None
                else: return int(x)

            def ism(a, b):
                r = 0
                if a is not None: r += a
                if b is not None: r += b
                return r

            ar = [iot(data['residents']), iot(data['entitled']), iot(data['cards']), iot(data['votes']),
                  iot(data['valid_votes']), ism(iot(data['votes_a']), iot(data['votes_b']))]
            ar = list(filter(lambda x: x is not None, ar))

            if not sorted(ar, reverse=True) == ar:
                return JsonResponse({'result':'invalid-data'})

            candidates = list(Candidate.objects.all())

            m.residents_no = iot(data['residents'])
            m.entitled_no = iot(data['entitled'])
            m.cards_no = iot(data['cards'])
            m.votes_no = iot(data['votes'])
            m.valid_votes_no = iot(data['valid_votes'])

            ra = m.results.filter(candidate__id=candidates[0].id).first()
            rb = m.results.filter(candidate__id=candidates[1].id).first()

            if not ra:
                ra = ElectionResult(candidate=candidates[0], municipality=m, votes=0)
            if not rb:
                rb = ElectionResult(candidate=candidates[1], municipality=m, votes=0)

            ra.votes = int(data['votes_a']) if data['votes_a'] else 0
            rb.votes = int(data['votes_b']) if data['votes_b'] else 0
            m.update_user = request.user

            m.save()
            ra.save()
            rb.save()
            return JsonResponse({'result': 'ok'})
    else:
        raise SuspiciousOperation("Should post!")


class ProviceViewSet(viewsets.ModelViewSet):
    queryset = Province.objects.all()
    serializer_class = ProvinceSerializer


class MunicipalityViewSet(viewsets.ModelViewSet):
    queryset = Municipality.objects.all()
    serializer_class = MunicipalitySerializer


class CandidateViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.all()
    serializer_class = CandidateSerializer


class ElectionResultsViewSet(viewsets.ModelViewSet):
    queryset = ElectionResult.objects.all()
    serializer_class = ElectionResultsSerializer


class MunicipalitySizesView(APIView):
    def get(self, request, *args, **kwargs):
        ctx = dict()

        possible_sizes = [
            (None, 5000),
            (5001, 10000),
            (10001, 20000),
            (20001, 50000),
            (50001, 100000),
            (100001, 200000),
            (200001, 500000),
            (500001, None)
        ]

        def make_query(r):
            a, b = r
            if a:
                ar = Q(municipality__residents_no__gt=a-1)
            if b:
                br = Q(municipality__residents_no__lt=b+1)

            if a and b:
                return ar & br
            elif a:
                return ar
            elif b:
                return br
            else:
                return Q()

        def make_name(r):
            return (
                (('od {} '.format(intcomma(r[0]))) if r[0] else '') + ('do {}'.format(intcomma(r[1])) if r[1] else '')
            ).strip()


        ctx['results'] = [
            {'name': make_name(r),
             'voting_results': {c.id: c.results.filter(make_query(r)).aggregate(sum=Coalesce(Sum('votes'), 0))['sum']
              for c in Candidate.objects.all()},
             'result_unit': {'type': 'size', 'from': r[0], 'to': r[1]}
            }
            for r in possible_sizes
        ]
        return Response(ctx, status=status.HTTP_200_OK)


class MunicipalityTypesView(APIView):
    def get(self, request, *args, **kwargs):
        ctx = dict()

        possible_types = [
            Municipality.Type.City,
            Municipality.Type.Village,
            Municipality.Type.Ship,
            Municipality.Type.Abroad
        ]

        def make_name(r):
            return Municipality.Type.values[r]


        ctx['results'] = [
            {'name': make_name(r),
             'voting_results': {c.id: c.results.filter(Q(municipality__type=r)).aggregate(sum=Coalesce(Sum('votes'), 0))['sum']
              for c in Candidate.objects.all()},
             'result_unit': {'type': 'type', 'id': r}
            }
            for r in possible_types
        ]
        return Response(ctx, status=status.HTTP_200_OK)


class MunicipalityQueryView(viewsets.ViewSet):
    def list(self, request):
        what = request.GET
        if 'type' not in what:
            return self.query_helper(Q())
        if what['type'] == 'province':
            pid = what['id']
            return self.query_helper(Q(province__id=pid))
        elif what['type'] == 'type':
            tid = what['id']
            return self.query_helper(Q(type=tid))
        elif what['type'] == 'size':
            rng = (int(what['from']) if what['from'] else None, int(what['to']) if what['to'] else None)

            def make_query(r):
                a, b = r
                if a:
                    ar = Q(residents_no__gt=a-1)
                if b:
                    br = Q(residents_no__lt=b+1)

                if a and b:
                    return ar & br
                elif a:
                    return ar
                elif b:
                    return br
                else:
                    return Q()
            return self.query_helper(make_query(rng))
        elif what['type'] == 'municipality':
            mid = what['id']
            return self.query_helper(Q(id=mid))
        else:
            raise SuspiciousOperation('Wrong query')

    def query_helper(self, q):
        objects = Municipality.objects.filter(q)
        serializer = MunicipalitySerializer(objects, many=True)
        return Response({'results': serializer.data})
