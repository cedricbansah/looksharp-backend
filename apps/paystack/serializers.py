from rest_framework import serializers


class BanksQuerySerializer(serializers.Serializer):
    type = serializers.CharField(required=False, default="mobile_money")
    currency = serializers.CharField(required=False, default="GHS")


class TransferRecipientCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    account_number = serializers.CharField(max_length=64)
    bank_code = serializers.CharField(max_length=20)
    type = serializers.CharField(required=False, default="mobile_money")
    currency = serializers.CharField(required=False, default="GHS")


class TransferCreateSerializer(serializers.Serializer):
    recipient = serializers.CharField(max_length=200)
    amount = serializers.IntegerField(min_value=1)
    reference = serializers.CharField(max_length=200)
    reason = serializers.CharField(required=False, default="LookSharp cashout")


class FinalizeTransferPathSerializer(serializers.Serializer):
    transfer_code = serializers.CharField(max_length=200)
