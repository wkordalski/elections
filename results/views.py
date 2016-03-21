from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.exceptions import SuspiciousOperation
from django.db.models.aggregates import Sum
from django.db.models.functions import Coalesce
from django.db.models.query_utils import Q
from django.shortcuts import render

from results.models import Municipality, Province, Candidate


class VotingStatistics:
    def __init__(self):
        self.residents_no = 0
        self.entitled_no = 0
        self.cards_no = 0
        self.votes_no = 0
        self.valid_votes_no = 0

    def add(self, statistics):
        self.residents_no += statistics.residents_no if statistics.residents_no else 0
        self.entitled_no += statistics.entitled_no if statistics.entitled_no else 0
        self.cards_no += statistics.cards_no if statistics.cards_no else 0
        self.votes_no += statistics.votes_no if statistics.votes_no else 0
        self.valid_votes_no += statistics.valid_votes_no if statistics.valid_votes_no else 0


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
    ctx['residents_no'] = statistics['poland']['voting']['residents']
    ctx['entitled_no'] = statistics['poland']['voting']['entitled']
    ctx['cards_no'] = statistics['poland']['voting']['cards']
    ctx['votes_no'] = statistics['poland']['voting']['votes']
    ctx['valid_votes_no'] = statistics['poland']['voting']['valid_votes']

    ctx['map_colors'] = dict()

    def assign_color_to_province(province):
        max_item = max(province['results'].items(), key=lambda x: x[1] if x[1] else -1)
        return statistics['colorizer'].scaled_color(max_item[0], max_item[1], province['voting']['sum'])

    for id, province in statistics['provinces'].items():
        if province['object'].map_id:
            ctx['map_colors'][province['object'].map_id] = assign_color_to_province(province)

    ctx['color_scale'] = statistics['colorizer'].get_scale()
    ctx['color_unknown'] = statistics['colorizer'].get_unknown_color()
    ctx['color_indecisive'] = statistics['colorizer'].get_indecisive_color()
    return ctx


def summary_window(request, statistics):
    ctx = dict()
    ctx['candidates'] = [
        (statistics['candidates'][i],
         statistics['colorizer'].color(statistics['candidates'][i].id),
         statistics['global']['results'][statistics['candidates'][i].id],
         (statistics['global']['results'][statistics['candidates'][i].id]*100/statistics['global']['voting']['sum']) if statistics['global']['voting']['sum'] > 0 else 0,)
        for i in range(len(statistics['candidates']))
    ]

    return ctx


def province_window(request, statistics):
    ctx = dict()

    colorizer = statistics['colorizer']

    ctx['candidates'] = statistics['candidates']
    lft = statistics['candidates'][0].id
    rgt = statistics['candidates'][1].id
    ctx['colors'] = [colorizer.color(lft), colorizer.color(rgt)]
    ctx['provinces'] = [
        (p['object'].name,
         p['voting']['sum'],
         p['results'][lft],
         (p['results'][lft]*100/p['voting']['sum']) if p['voting']['sum'] > 0 else 0,
         p['results'][rgt],
         (p['results'][rgt]*100/p['voting']['sum']) if p['voting']['sum'] > 0 else 0,)
        for pid, p in statistics['provinces'].items()
    ]
    ctx['provinces'].sort(key=lambda x: x[0])

    ctx['poland'] = (
        statistics['poland']['voting']['sum'],
        statistics['poland']['results'][lft],
        (statistics['poland']['results'][lft]*100/statistics['poland']['voting']['sum']) if statistics['poland']['voting']['sum'] > 0 else 0,
        statistics['poland']['results'][rgt],
        (statistics['poland']['results'][rgt]*100/statistics['poland']['voting']['sum']) if statistics['poland']['voting']['sum'] > 0 else 0,
    )

    return ctx


def municipality_window(request, statistics):
    ctx = dict()

    colorizer = statistics['colorizer']

    ctx['candidates'] = statistics['candidates']
    lft = statistics['candidates'][0].id
    rgt = statistics['candidates'][1].id
    ctx['colors'] = [colorizer.color(lft), colorizer.color(rgt)]
    type_stats = statistics['municipality_type']
    ctx['municipality_types'] = [
        (Municipality.Type.values[t],
         type_stats[t]['voting']['sum'],
         type_stats[t]['results'][lft],
         (type_stats[t]['results'][lft] * 100 / type_stats[t]['voting']['sum']) if type_stats[t]['voting']['sum'] > 0 else 0,
         type_stats[t]['results'][rgt],
         (type_stats[t]['results'][rgt] * 100 / type_stats[t]['voting']['sum']) if type_stats[t]['voting']['sum'] > 0 else 0,
         )
        for t in list(['C', 'V', 'S', 'A'])
    ]

    ctx['municipality_sizes'] = [
        (
            (('od {} '.format(intcomma(ms[0]+1))) if ms[0] > 0 else '') + ('do {}'.format(intcomma(ms[1]))),
            ms[2]['voting']['sum'],
            ms[2]['results'][lft],
            (ms[2]['results'][lft] * 100 / ms[2]['voting']['sum']) if ms[2]['voting']['sum'] > 0 else 0,
            ms[2]['results'][rgt],
            (ms[2]['results'][rgt] * 100 / ms[2]['voting']['sum']) if ms[2]['voting']['sum'] > 0 else 0,
        )
        for ms in statistics['municipality_size']
    ]
    ctx['municipality_sizes'].insert(0,
        (
            'Statki i zagranica',
            type_stats['S']['voting']['sum'] + type_stats['A']['voting']['sum'],
            type_stats['S']['results'][lft] + type_stats['A']['results'][lft],
            ((type_stats['S']['results'][lft] + type_stats['A']['results'][lft]) * 100 / (type_stats['S']['voting']['sum'] + type_stats['A']['voting']['sum'])) if (type_stats['S']['voting']['sum'] + type_stats['A']['voting']['sum']) > 0 else 0,
            type_stats['S']['results'][rgt] + type_stats['A']['results'][rgt],
            ((type_stats['S']['results'][rgt] + type_stats['A']['results'][rgt]) * 100 / (type_stats['S']['voting']['sum'] + type_stats['A']['voting']['sum'])) if (type_stats['S']['voting']['sum'] + type_stats['A']['voting']['sum']) > 0 else 0,
        )
    )
    big_mun = statistics['municipality_biggest_size']
    ctx['municipality_sizes'].append(
        (
            ('pow. {}'.format(intcomma(big_mun[0]))),
            big_mun[1]['voting']['sum'],
            big_mun[1]['results'][lft],
            (big_mun[1]['results'][lft] * 100 / big_mun[1]['voting']['sum']) if big_mun[1]['voting']['sum'] > 0 else 0,
            big_mun[1]['results'][rgt],
            (big_mun[1]['results'][rgt] * 100 / big_mun[1]['voting']['sum']) if big_mun[1]['voting']['sum'] > 0 else 0,
        )
    )

    return ctx


def index(request):
    stats = dict()
    ctx = dict()

    def ntz(v):
        return 0 if v is None else v

    candidates = list(Candidate.objects.all())
    stats['candidates'] = candidates

    if len(candidates) != 2:
        raise SuspiciousOperation(
            'Website admins are not good enough to provide valid voting results - there is third candidate.'
        )

    colorizer = color_conf(stats)
    stats['colorizer'] = colorizer

    candidate_votes = {c.id: c.results.aggregate(Sum('votes')) for c in Candidate.objects.all()}
    stats['candidate_votes'] = candidate_votes

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

    def merge_dicts(d, *args):
        nd = d.copy()
        for a in args:
            nd.update(a)
        return nd

    stats['global'] = aggregate_votings(Q(), Q())

    poland_municipality_filter = Q(type=Municipality.Type.City) | Q(type=Municipality.Type.Village)
    poland_result_filter = Q(municipality__type=Municipality.Type.City) | Q(municipality__type=Municipality.Type.Village)

    stats['poland'] = aggregate_votings(poland_municipality_filter, poland_result_filter)

    stats['provinces'] = {p.id: merge_dicts({'object': p}, aggregate_votings(Q(province__id=p.id), Q(municipality__province__id=p.id)))
                                for p in Province.objects.all()}

    stats['municipality_type'] = {t: aggregate_votings(Q(type=t), Q(municipality__type=t))
                                  for t in Municipality.Type.values}

    municipality_sizes = [0, 5000, 10000, 20000, 50000, 100000, 200000, 500000]

    stats['municipality_size'] = [(
        municipality_sizes[i], municipality_sizes[i+1],
        aggregate_votings(poland_municipality_filter & Q(residents_no__lt=municipality_sizes[i+1]+1, residents_no__gt=municipality_sizes[i]), poland_result_filter & Q(municipality__residents_no__lt=municipality_sizes[i+1]+1, municipality__residents_no__gt=municipality_sizes[i]))
    ) for i in range(len(municipality_sizes)-1)]
    stats['municipality_biggest_size'] = (
        municipality_sizes[-1],
        aggregate_votings(poland_municipality_filter & Q(residents_no__gt=municipality_sizes[-1]),
                          poland_result_filter & Q(municipality__residents_no__gt=municipality_sizes[-1])
                         )
    )

    ctx['map_window'] = map_window(request, stats)
    ctx['summary_window'] = summary_window(request, stats)
    ctx['province_window'] = province_window(request, stats)
    ctx['municipality_window'] = municipality_window(request, stats)

    return render(request, 'results/compare.html', ctx)
