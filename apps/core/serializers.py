from rest_framework import serializers


class EnumOptionSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


class SurveyCategoryConfigSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    icon = serializers.CharField(allow_blank=True)
    survey_count = serializers.IntegerField()


class OfferCategoryConfigSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    icon = serializers.CharField(allow_blank=True)
    offer_count = serializers.IntegerField()


class ConfigEnumsResponseSerializer(serializers.Serializer):
    survey_statuses = EnumOptionSerializer(many=True)
    question_types = EnumOptionSerializer(many=True)
    offer_statuses = EnumOptionSerializer(many=True)
    verification_statuses = EnumOptionSerializer(many=True)
    withdrawal_statuses = EnumOptionSerializer(many=True)
    network_providers = EnumOptionSerializer(many=True)
    id_types = EnumOptionSerializer(many=True)
    genders = EnumOptionSerializer(many=True)
    survey_categories = SurveyCategoryConfigSerializer(many=True)
    offer_categories = OfferCategoryConfigSerializer(many=True)
