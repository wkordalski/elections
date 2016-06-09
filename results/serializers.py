from rest_framework import serializers

from results.models import Municipality, Candidate, Province, ElectionResult


class CandidateSerializer(serializers.ModelSerializer):
    voting_results = serializers.ReadOnlyField()

    class Meta:
        model = Candidate
        fields = ('id', 'name', 'surname', 'voting_results')


class ProvinceSerializer(serializers.ModelSerializer):
    voting_results = serializers.ReadOnlyField()
    result_unit = serializers.ReadOnlyField()


    class Meta:
        model = Province
        fields = ('id', 'name', 'map_id', 'voting_results', 'result_unit')


class MunicipalitySerializer(serializers.ModelSerializer):
    voting_results = serializers.ReadOnlyField()
    update_token = serializers.ReadOnlyField()

    class Meta:
        model = Municipality
        fields = ('id', 'name', 'province', 'results', 'voting_results', 'residents_no', 'entitled_no', 'cards_no', 'votes_no', 'valid_votes_no', 'update_time', 'update_user', 'update_token')


class ElectionResultsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectionResult
        fields = ('candidate', 'municipality', 'votes')
