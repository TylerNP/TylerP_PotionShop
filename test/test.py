from src.api import barrels, bottler
from src.api.barrels import Barrel
import unittest

"""
Test Barrel Plan Logic
"""
class TestBarrelFunctions(unittest.TestCase):
    barrel_catalog = [
                        Barrel(sku='MEDIUM_RED_BARREL', ml_per_barrel=2500, potion_type=[1, 0, 0, 0], price=250, quantity=10), 
                        Barrel(sku='SMALL_RED_BARREL', ml_per_barrel=500, potion_type=[1, 0, 0, 0], price=100, quantity=10), 
                        Barrel(sku='MEDIUM_GREEN_BARREL', ml_per_barrel=2500, potion_type=[0, 1, 0, 0], price=250, quantity=10), 
                        Barrel(sku='SMALL_GREEN_BARREL', ml_per_barrel=500, potion_type=[0, 1, 0, 0], price=100, quantity=10), 
                        Barrel(sku='MEDIUM_BLUE_BARREL', ml_per_barrel=2500, potion_type=[0, 0, 1, 0], price=300, quantity=10),
                        Barrel(sku='SMALL_BLUE_BARREL', ml_per_barrel=500, potion_type=[0, 0, 1, 0], price=120, quantity=10), 
                        Barrel(sku='MINI_RED_BARREL', ml_per_barrel=200, potion_type=[1, 0, 0, 0], price=60, quantity=1), 
                        Barrel(sku='MINI_GREEN_BARREL', ml_per_barrel=200, potion_type=[0, 1, 0, 0], price=60, quantity=1), 
                        Barrel(sku='MINI_BLUE_BARREL', ml_per_barrel=200, potion_type=[0, 0, 1, 0], price=60, quantity=1), 
                        Barrel(sku='LARGE_DARK_BARREL', ml_per_barrel=10000, potion_type=[0, 0, 0, 1], price=750, quantity=10), 
                        Barrel(sku='LARGE_BLUE_BARREL', ml_per_barrel=10000, potion_type=[0, 0, 1, 0], price=600, quantity=30), 
                        Barrel(sku='LARGE_GREEN_BARREL', ml_per_barrel=10000, potion_type=[0, 1, 0, 0], price=400, quantity=30), 
                        Barrel(sku='LARGE_RED_BARREL', ml_per_barrel=10000, potion_type=[1, 0, 0, 0], price=500, quantity=30),
                         Barrel(sku='LARGE_DARK_BARREL', ml_per_barrel=10000, potion_type=[0, 0, 0, 1], price=750, quantity=30)
                    ]
    def test_plan_simplified_1(self):
        expected = [
                        {'sku': 'MEDIUM_RED_BARREL', 'quantity': 3}, 
                        {'sku': 'MEDIUM_GREEN_BARREL', 'quantity': 2}, 
                        {'sku': 'MEDIUM_BLUE_BARREL', 'quantity': 1}, 
                        {'sku': 'LARGE_DARK_BARREL', 'quantity': 1}, 
                        {'sku': 'SMALL_RED_BARREL', 'quantity': 2}
                    ]
        ml_needed = [5000,1000,500,0]
        ml_stored = [1000,500,500,0]
        usable_gold = 2500
        small_gold = 500
        ml_capacity = 40000
        self.assertEqual(barrels.simplified_plan(TestBarrelFunctions.barrel_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity), expected)
    def test_plan_simplified_2(self):
        expected = [
                        {'sku': 'SMALL_RED_BARREL', 'quantity': 2}, 
                        {'sku': 'SMALL_GREEN_BARREL', 'quantity': 1}, 
                        {'sku': 'SMALL_BLUE_BARREL', 'quantity': 1}, 
                        {'sku': 'MINI_GREEN_BARREL', 'quantity': 1}
                    ]
        ml_needed = [1000,1000,500,0]
        ml_stored = [100,500,500,0]
        usable_gold = 500
        small_gold = 500
        ml_capacity = 10000
        
        self.assertEqual(barrels.simplified_plan(TestBarrelFunctions.barrel_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity), expected)
    def test_plan_simplified_3(self):
        expected = [
                        {'sku': 'SMALL_RED_BARREL', 'quantity': 1}, 
                        {'sku': 'SMALL_GREEN_BARREL', 'quantity': 1}, 
                        {'sku': 'SMALL_BLUE_BARREL', 'quantity': 1}, 
                        {'sku': 'MINI_RED_BARREL', 'quantity': 1}, 
                        {'sku': 'MINI_GREEN_BARREL', 'quantity': 1}, 
                        {'sku': 'MINI_BLUE_BARREL', 'quantity': 1}
                    ]
        ml_needed = [1000,1000,500,0]
        ml_stored = [2500,2500,2500,0]
        usable_gold = 500
        small_gold = 500
        ml_capacity = 10000
        self.assertEqual(barrels.simplified_plan(TestBarrelFunctions.barrel_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity), expected)
    def test_plan_simplified_4(self):
        expected = [
                        {'sku': 'MEDIUM_RED_BARREL', 'quantity': 1}, 
                        {'sku': 'MEDIUM_GREEN_BARREL', 'quantity': 1}, 
                        {'sku': 'MEDIUM_BLUE_BARREL', 'quantity': 1}, 
                        {'sku': 'MINI_RED_BARREL', 'quantity': 1}, 
                        {'sku': 'MINI_GREEN_BARREL', 'quantity': 1}, 
                        {'sku': 'MINI_BLUE_BARREL', 'quantity': 1}
                    ]
        ml_needed = [0,0,0,0]
        ml_stored = [500,500,500,0]
        usable_gold = 1500
        small_gold = 500
        ml_capacity = 10000
        self.assertEqual(barrels.simplified_plan(TestBarrelFunctions.barrel_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity), expected)
    def test_plan_simplified_5(self):
        expected = [
                        {'sku': 'MEDIUM_GREEN_BARREL', 'quantity': 1}, 
                        {'sku': 'MEDIUM_BLUE_BARREL', 'quantity': 1}, 
                        {'sku': 'MINI_GREEN_BARREL', 'quantity': 1}, 
                        {'sku': 'MINI_BLUE_BARREL', 'quantity': 1}
                    ]
        ml_needed = [0,0,0,0]
        ml_stored = [3500,500,500,0]
        usable_gold = 1500
        small_gold = 500
        ml_capacity = 10000
        self.assertEqual(barrels.simplified_plan(TestBarrelFunctions.barrel_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity), expected)

class TestBottlerFunctions(unittest.TestCase):
    def test_plan_1(self):
        self.assertEqual()

if __name__ == '__main__':
    unittest.main()