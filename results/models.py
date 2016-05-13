from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django.db import models
from django.db.models.aggregates import Count
from djchoices import DjangoChoices, ChoiceItem


class Candidate(models.Model):
    class Meta:
        verbose_name = "Kandydat"
        verbose_name_plural = "Kandydaci"
        ordering = ['surname']

    def validate_unique(self, exclude=None):
        super(Candidate, self).validate_unique(exclude)

        if self._state.adding and self.pk is None and self.__class__._default_manager.count() >= 2:
            raise ValidationError({
                NON_FIELD_ERRORS: ['W bazie danych są już dwaj kandydaci.'],
            })

    def __str__(self):
        return self.surname + ' ' + self.name

    def votes_no(self):
        return sum([r.votes if r.votes else 0 for r in self.results.all()])
    votes_no.short_description = '# głosów'

    name = models.CharField('Imię', max_length=64)
    surname = models.CharField('Nazwisko', max_length=64)


class Province(models.Model):
    class Meta:
        verbose_name = "Województwo"
        verbose_name_plural = "Województwa"

    name = models.CharField('Nazwa', max_length=256)
    map_id = models.CharField('Identyfikator na mapie', max_length=8, null=True, blank=True)

    def residents_no(self):
        return sum([m.residents_no if m.residents_no else 0 for m in self.municipalities.all()])
    residents_no.short_description = '# mieszkańców'

    def entitled_no(self):
        return sum([m.entitled_no if m.entitled_no else 0 for m in self.municipalities.all()])
    entitled_no.short_description = '# uprawnionych'

    def cards_no(self):
        return sum([m.cards_no if m.cards_no else 0 for m in self.municipalities.all()])
    cards_no.short_description = '# wydanych kart'

    def municipalities_no(self):
        return self.municipalities.count()
    municipalities_no.short_description = '# gmin'

    def votes_of_candidates(self):
        result = dict()
        for m in self.municipalities.all():
            for r in m.results.all():
                if r.candidate.id in result:
                    result[r.candidate.id] += r.votes
                else:
                    result[r.candidate.id] = r.votes
        return result

    def __str__(self):
        return self.name


class Municipality(models.Model):
    class Meta:
        verbose_name = 'Gmina'
        verbose_name_plural = "Gminy"
        unique_together = ('province', 'name')

    class Type(DjangoChoices):
        City = ChoiceItem('C', label="Miasto")
        Village = ChoiceItem('V', label="Wieś")
        Ship = ChoiceItem('S', label="Statek")
        Abroad = ChoiceItem('A', label="Zagranica")

    def clean(self):
        edict = dict()
        max_ppl = self.residents_no

        if self.entitled_no:
            if max_ppl and self.entitled_no > max_ppl:
                edict['entitled_no'] = '# entitled is greater then # residents.'
            else:
                max_ppl = self.entitled_no

        if self.cards_no:
            if max_ppl and self.cards_no > max_ppl:
                edict['cards_no'] = '# cards is too large.'
            else:
                max_ppl = self.cards_no

        if self.votes_no:
            if max_ppl and self.votes_no > max_ppl:
                edict['votes_no'] = '# votes is too large.'
            else:
                max_ppl = self.votes_no

        if self.valid_votes_no:
            if max_ppl and self.valid_votes_no > max_ppl:
                edict['valid_votes_no'] = '# valid votes is too large'

        if len(edict) > 0: raise ValidationError(edict)

    def is_fully_filled(self):
        if not self.residents_no: return False
        if not self.entitled_no: return False
        if not self.cards_no: return False
        if not self.votes_no: return False
        if not self.valid_votes_no: return False

        if sum([r.votes for r in self.results.all()]) != self.valid_votes_no:
            return False
        return True
    is_fully_filled.boolean = True
    is_fully_filled.short_description = 'Poprawne?'

    name = models.CharField('Nazwa', max_length=256)
    type = models.CharField('Typ', max_length=1, choices=Type.choices, validators=[Type.validator])
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name='municipalities', verbose_name='Województwo', null=True, blank=True)

    residents_no = models.PositiveIntegerField('# mieszkańców', null=True, blank=True)
    entitled_no = models.PositiveIntegerField('# uprawnionych', null=True, blank=True)
    cards_no = models.PositiveIntegerField('# wydanych kart', null=True, blank=True)
    votes_no = models.PositiveIntegerField('# oddanych głosów', null=True, blank=True)
    valid_votes_no = models.PositiveIntegerField('# ważnych głosów', null=True, blank=True)

    update_time = models.DateTimeField(null=True, auto_now=True, verbose_name='Czas modyfikacji')
    update_user = models.ForeignKey(User, on_delete=models.SET_NULL, verbose_name='Modyfikator', null=True)


    def __str__(self):
        return self.name + ' w ' + self.province.name


class ElectionResult(models.Model):
    class Meta:
        unique_together = ('candidate', 'municipality')

    def __str__(self):
        return str(self.candidate) + ' w gminie ' + str(self.municipality)

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='results')
    municipality = models.ForeignKey(Municipality, on_delete=models.CASCADE, related_name='results')
    votes = models.PositiveIntegerField(default=0)
