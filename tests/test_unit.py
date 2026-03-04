from inf349.services import calculate_shipping_price, TAX_RATES


class TestCalculateShippingPrice:
    def test_under_500g(self):
        assert calculate_shipping_price(100) == 5
        assert calculate_shipping_price(499) == 5
        assert calculate_shipping_price(500) == 5

    def test_between_500g_and_2kg(self):
        assert calculate_shipping_price(501) == 10
        assert calculate_shipping_price(1000) == 10
        assert calculate_shipping_price(2000) == 10

    def test_over_2kg(self):
        assert calculate_shipping_price(2001) == 25
        assert calculate_shipping_price(5000) == 25


class TestTaxRates:
    def test_quebec(self):
        assert TAX_RATES["QC"] == 0.15

    def test_ontario(self):
        assert TAX_RATES["ON"] == 0.13

    def test_alberta(self):
        assert TAX_RATES["AB"] == 0.05

    def test_british_columbia(self):
        assert TAX_RATES["BC"] == 0.12

    def test_nova_scotia(self):
        assert TAX_RATES["NS"] == 0.14

    def test_tax_calculation_qc(self):
        total_price = 9148
        tax_rate = TAX_RATES["QC"]
        total_price_tax = round(total_price * (1 + tax_rate), 2)
        assert total_price_tax == 10520.2
