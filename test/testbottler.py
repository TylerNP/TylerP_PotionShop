from src.api import bottler
import unittest
from src.api.barrels import simplified_plan as barrel_plan

"""
Test Bottler Plan Logic
"""
class TestBottlerFunctions(unittest.TestCase):
    def test_plan_1(self):
        brew_amt = [48, 33, 26, 23]
        ml_stored = [28705, 35561, 30335, 31599]
        unique_potions = [[25, 35, 10, 30], [2, 4, 90, 4], [94, 2, 2, 2], [50, 25, 10, 15]]
        storage_left = 423
        result = bottler.bottle_plan_calculation(brew_amt, ml_stored, unique_potions, storage_left)
        expected = [
            {'potion_type': [25, 35, 10, 30], 'quantity': 48}, 
            {'potion_type': [2, 4, 90, 4], 'quantity': 33}, 
            {'potion_type': [94, 2, 2, 2], 'quantity': 26}, 
            {'potion_type': [50, 25, 10, 15], 'quantity': 23}
        ]
        self.assertEqual(result, expected)

    def test_plan_2(self):
        brew_amt = [25, 25, 25, 25]
        ml_stored = [300, 561, 335, 599]
        unique_potions = [[25, 35, 10, 30], [2, 4, 90, 4], [94, 2, 2, 2], [50, 25, 10, 15]]
        storage_left = 423
        result = bottler.bottle_plan_calculation(brew_amt, ml_stored, unique_potions, storage_left)
        expected = [
            {'potion_type': [25, 35, 10, 30], 'quantity': 2}, 
            {'potion_type': [2, 4, 90, 4], 'quantity': 3}, 
            {'potion_type': [94, 2, 2, 2], 'quantity': 2}, 
            {'potion_type': [50, 25, 10, 15], 'quantity': 1}
        ]
        self.assertEqual(result, expected)

    def test_plan_3(self):
        brew_amt = [25, 25, 25, 25]
        ml_stored = [0, 0, 0, 0]
        unique_potions = [[25, 35, 10, 30], [2, 4, 90, 4], [94, 2, 2, 2], [50, 25, 10, 15]]
        storage_left = 423
        result = bottler.bottle_plan_calculation(brew_amt, ml_stored, unique_potions, storage_left)
        expected = []
        self.assertEqual(result, expected)

    def test_plan_4(self):
        brew_amt = [0, 0, 0, 0]
        ml_stored = [1000, 1000, 1000, 1000]
        unique_potions = [[25, 35, 10, 30], [2, 4, 90, 4], [94, 2, 2, 2], [50, 25, 10, 15]]
        storage_left = 50
        result = bottler.bottle_plan_calculation(brew_amt, ml_stored, unique_potions, storage_left)
        expected = []
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()