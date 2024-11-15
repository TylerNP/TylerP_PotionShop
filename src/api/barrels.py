from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth

import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    """ 
    Updates the database information with the barrels bought
    """
    print(f"Delivery {order_id} For {barrels_delivered}")
    count = 0
    gold_cost = 0
    ml_type = ["red", "green", "blue", "dark"]
    ml_bought = [0]*4

    for barrel in barrels_delivered:
        count += barrel.quantity
        gold_cost += barrel.quantity*barrel.price
        for index in range(len(ml_type)):
            ml_bought[index] += barrel.ml_per_barrel*barrel.quantity*barrel.potion_type[index]
        
    with db.engine.begin() as connection: 
        values = {
                        "gold_cost":gold_cost, 
                        "red":ml_bought[0], 
                        "green":ml_bought[1], 
                        "blue":ml_bought[2], 
                        "dark":ml_bought[3],
                        "order_id":order_id,
                }
        sql_to_execute = """
                            INSERT INTO transactions (description, time_id, order_id)
                            VALUES (
                                    'Bought ' ||  
                                    :red || ' red ml ' || 
                                    :green || ' green ml ' || 
                                    :blue || ' blue ml ' || 
                                    :dark || ' dark ml for ' || 
                                    :gold_cost, 
                                    (SELECT MAX(time.id) FROM time LIMIT 1),
                                    :order_id
                                    ) 
                            RETURNING id
                        """
        values["transaction_id"] = connection.execute(sqlalchemy.text(sql_to_execute), values).scalar()
        sql_to_execute = """
                            INSERT INTO ml_ledgers (num_red_ml, num_green_ml, num_blue_ml, num_dark_ml, transaction_id)
                            VALUES (:red, :green, :blue, :dark, :transaction_id)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
        sql_to_execute = """
                            INSERT INTO gold_ledgers (gold, transaction_id)
                            VALUES (-1*:gold_cost, :transaction_id)
                        """
        connection.execute(sqlalchemy.text(sql_to_execute), values)
    for index in range(len(ml_type)):
        print("Bought %d %s ml" % (ml_bought[index], ml_type[index]))
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ 
    Process available barrels for sale and returns what barrels to be bought
    """

    print(f"Available barrels: {wholesale_catalog}")
    #TO DO improve barrel planning logic

    usable_gold = 0
    ml_capacity = 0
    small_gold = 0
    num_types = 4
    ml_needed = [0]*num_types
    ml_stored = [0]*num_types

    with db.engine.begin() as connection: 
        sql_to_execute = """
            SELECT 
                (10000*(SELECT ml_capacity FROM global_inventory)) AS capacity, 
                ((SELECT SUM(gold) FROM gold_ledgers)-(SELECT gold_threshold FROM parameters)) AS usable_gold, 
                (SELECT starting_gold_saving FROM parameters) AS small_gold,
                SUM(num_red_ml)::int AS num_red_ml, 
                SUM(num_green_ml)::int AS num_green_ml, 
                SUM(num_blue_ml)::int AS num_blue_ml, 
                SUM(num_dark_ml)::int AS num_dark_ml 
            FROM ml_ledgers
        """
        query = connection.execute(sqlalchemy.text(sql_to_execute))
        for result in query:
            ml_capacity = result.capacity
            usable_gold = result.usable_gold
            small_gold = result.small_gold
            ml_stored[0] = result.num_red_ml
            ml_stored[1] = result.num_green_ml
            ml_stored[2] = result.num_blue_ml
            ml_stored[3] = result.num_dark_ml
        
        #ml Needed For Immediate Brewing
        sql_to_execute = """
            SELECT result.threshold, SUM(potion_ledgers.quantity) AS quantity, red, green, blue, dark 
            FROM potions, potion_ledgers, (
                SELECT (potion_capacity * 50 / (
                    SELECT COUNT(1) 
                    FROM potions 
                    WHERE brew = TRUE)) AS threshold 
                FROM global_inventory) AS result
            WHERE brew = TRUE 
            AND potions.sku = potion_ledgers.sku
            GROUP BY
                potion_ledgers.sku,
                result.threshold,
                red, green, blue, dark
            HAVING 
                SUM(potion_ledgers.quantity) < result.threshold
        """
        specific_pots = connection.execute(sqlalchemy.text(sql_to_execute))
        for pots in specific_pots:
            ml_needed[0] += pots.red*(pots.threshold-pots.quantity)
            ml_needed[1] += pots.green*(pots.threshold-pots.quantity)
            ml_needed[2] += pots.blue*(pots.threshold-pots.quantity)
            ml_needed[3] += pots.dark*(pots.threshold-pots.quantity)

    return barrel_plan_calculation(wholesale_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity)

def barrel_plan_calculation(
    wholesale_catalog : list[Barrel], 
    ml_needed : list[int], 
    ml_stored : list[int],
    usable_gold : int,
    small_gold : int,
    ml_capacity : int
) -> dict[str, any]:
    plan = []
    num_types = 4

    if sum(ml_stored) == ml_capacity:
        return plan
    ml_count = sum(1 for ml in ml_needed if ml != 0)
    if ml_count == 0:
        ml_count = num_types
    if usable_gold < small_gold:
        ml_count = 1

    desired_barrels = []
    barrel_types = [[] for _ in range(num_types)]
    for barrel in wholesale_catalog:
        if barrel.price > usable_gold//ml_count or barrel.ml_per_barrel > ml_capacity//num_types:
            continue
        desired_barrels.append(barrel)
    sorted_barrels = sorted(desired_barrels, key=lambda x: x.ml_per_barrel//x.price, reverse=True)

    barrel_type = 1
    for barrel in sorted_barrels:
        barrel_types[barrel.potion_type.index(barrel_type)].append(barrel)

    ml_threshold = ml_capacity//num_types
    not_buying_count = 0
    overflow_ml = 0
    ml_can_buy = [0]*num_types
    for index in range(num_types):
        if len(barrel_types[index]) > 0 and ml_stored[index] <= ml_threshold:
            ml_can_buy[index] = 1
        else:
            not_buying_count += 1
            overflow_ml += ml_stored[index]

    if num_types == not_buying_count:
        return plan
    elif not_buying_count > 0:
        ml_threshold = (ml_capacity-overflow_ml) // (num_types-not_buying_count)

    minimum_ml_buyable = 200 # mini barrel amount
    ml_space = [0]*num_types

    for index in range(num_types):
        ml_space_remain = ml_threshold-ml_stored[index]
        if ml_can_buy[index] == 0:
            continue
        if ml_space_remain >= minimum_ml_buyable:
            ml_space[index] = ml_space_remain
        else:
            not_buying_count += 1
            ml_can_buy[index] = 0

    if (num_types-not_buying_count) == 1:
        ml_space[ml_space.index(max(ml_space))] = ml_capacity-sum(ml_stored)

    make_int = 10
    normal = sum(x*y for x, y in zip(ml_needed, ml_space))
    min_space = min([ml for ml in ml_space if ml > 0], default=0)
    normal = normal if normal != 0 else min_space*make_int
    ml_ratio = [0]*num_types

    for i in range(len(ml_needed)):
        if ml_can_buy[i] == 0:
            continue
        ml_ratio[i] = round(ml_needed[i]*ml_space[i]*make_int/normal) or 1

    ml_ratio_copy = ml_ratio.copy()
    max_index = ml_ratio.index(max(ml_ratio))
    type_index = max_index
    list_of_index = [0]*num_types
    buy_count = []
    unique_barrels = []
    
    count = 0
    MAX_ITERATIONS = 5000
    while any (buy != 0 for buy in ml_can_buy):
        count += 1
        if count > MAX_ITERATIONS:
            print("BAD LOOP GET HELP")
            break
        if all(ml <= 0 for ml in ml_ratio_copy):
            ml_ratio_copy = [ml_ratio[i]+ml_ratio_copy[i] for i in range(num_types)]
            type_index = max_index
        if ml_ratio_copy[type_index] <= 0 or ml_can_buy[type_index] == 0:
            type_index = (type_index+1) % num_types
            continue
        if list_of_index[type_index] >= len(barrel_types[type_index]):
            ml_can_buy[type_index] = 0
            ml_ratio_copy[type_index] = 0
            ml_ratio[type_index] = 0
            continue
        barrel_to_buy = barrel_types[type_index][list_of_index[type_index]]
        if (usable_gold < barrel_to_buy.price) or (ml_space[type_index] < barrel_to_buy.ml_per_barrel):
            list_of_index[type_index] = list_of_index[type_index] + 1
            continue   
        buy_amt = 1
        usable_gold -= barrel_to_buy.price
        ml_space[type_index] -= barrel_to_buy.ml_per_barrel
        if barrel_to_buy not in unique_barrels:
            unique_barrels.append(barrel_to_buy)
            buy_count.append(buy_amt)
        else:
            new_quantity = buy_count[unique_barrels.index(barrel_to_buy)] + buy_amt
            if new_quantity > barrel_to_buy.quantity:
                list_of_index[type_index] += 1
                continue
            buy_count[unique_barrels.index(barrel_to_buy)] = new_quantity
        relative_change = round(barrel_to_buy.ml_per_barrel*make_int/normal) or buy_amt # Ensure ratio is updated by at least buying amount
        ml_ratio_copy[type_index] -= relative_change
        type_index = (type_index+1) % num_types 
    
    print(f"Looped {count} times")
    total_color = [0]*4
    for i in range(len(unique_barrels)):
        plan.append( {"sku":unique_barrels[i].sku, "quantity": buy_count[i]} )
        total_color[unique_barrels[i].potion_type.index(1)] += unique_barrels[i].ml_per_barrel * buy_count[i]
    print(total_color)
    print(plan)
    return plan  


# Duplicate of barrel_plan_calcuation Where Changes Are Tested
def simplified_plan(
    wholesale_catalog : list[Barrel], 
    ml_needed : list[int], 
    ml_stored : list[int],
    usable_gold : int,
    small_gold : int,
    ml_capacity : int
) -> dict[str, any]:
    plan = []
    num_types = 4

    total_ml = sum(ml_stored)
    if total_ml == ml_capacity:
        return plan
    ml_count = sum(1 for ml in ml_needed if ml != 0)
    if ml_count == 0:
        ml_count = num_types
    if usable_gold < small_gold:
        ml_count = 1

    #Filter barrels purchasable with gold split between types possible needed and sort by ml per gold
    desired_barrels = []
    barrel_types = [[] for _ in range(num_types)]
    for barrel in wholesale_catalog:
        if barrel.price > usable_gold//ml_count or barrel.ml_per_barrel > ml_capacity//num_types:
            continue
        desired_barrels.append(barrel)
    sorted_barrels = sorted(desired_barrels, key=lambda x: x.ml_per_barrel//x.price, reverse=True)

    #Sort Barrels By Type [R,G,B,D]
    barrel_type = 1
    for barrel in sorted_barrels:
        barrel_types[barrel.potion_type.index(barrel_type)].append(barrel)

    #determine how much space is available
    ml_threshold = ml_capacity//num_types
    not_buying_count = 0
    overflow_ml = 0
    ml_can_buy = [0]*num_types
    for index in range(num_types):
        if len(barrel_types[index]) > 0 and ml_stored[index] <= ml_threshold:
            ml_can_buy[index] = 1
        else:
            not_buying_count += 1
            overflow_ml += ml_stored[index]

    if num_types == not_buying_count:
        return plan
    elif not_buying_count > 0:
        ml_threshold = (ml_capacity-overflow_ml) // (num_types-not_buying_count)

    minimum_ml_buyable = total_ml // 40 # min barrel amount
    ml_space = [0]*num_types

    for index in range(num_types):
        ml_space_remain = ml_threshold-ml_stored[index]
        if ml_can_buy[index] == 0:
            continue
        if ml_space_remain >= minimum_ml_buyable:
            ml_space[index] = ml_space_remain
        else:
            not_buying_count += 1
            ml_can_buy[index] = 0

    if (num_types-not_buying_count) == 1:
        ml_space[ml_space.index(max(ml_space))] = ml_capacity-sum(ml_stored)

    # Takes Dotproduct of ml_needed and ml_space and normalize to create weights for buying
    make_int = 10
    normal = sum(x*y for x, y in zip(ml_needed, ml_space))
    min_space = min([ml for ml in ml_space if ml > 0], default=0)
    normal = normal if normal != 0 else min_space*make_int
    ml_ratio = [0]*num_types

    for i in range(len(ml_needed)):
        if ml_can_buy[i] == 0:
            continue
        ml_ratio[i] = round(ml_needed[i]*ml_space[i]*make_int/normal) or 1 # Ensure To Refill Stock Even if not needed for brewing
    
    ml_ratio_copy = ml_ratio.copy()
    max_index = ml_ratio.index(max(ml_ratio))
    type_index = max_index
    list_of_index = [0]*num_types
    buy_count = []
    unique_barrels = []
    
    #Determine If More ml Can Be Purchased For Later use
    count = 0
    MAX_ITERATIONS = 5000
    while any (buy != 0 for buy in ml_can_buy):
        count += 1
        if count > MAX_ITERATIONS:
            print("BAD LOOP GET HELP")
            break
        if all(ml <= 0 for ml in ml_ratio_copy):
            ml_ratio_copy = [ml_ratio[i]+ml_ratio_copy[i] for i in range(num_types)]
            type_index = max_index
        if ml_ratio_copy[type_index] <= 0 or ml_can_buy[type_index] == 0:
            type_index = (type_index+1) % num_types
            continue
        if list_of_index[type_index] >= len(barrel_types[type_index]):
            ml_can_buy[type_index] = 0
            ml_ratio_copy[type_index] = 0
            ml_ratio[type_index] = 0
            continue
        barrel_to_buy = barrel_types[type_index][list_of_index[type_index]]
        if barrel_to_buy.ml_per_barrel < minimum_ml_buyable:
            ml_can_buy[type_index] = 0
            ml_ratio_copy[type_index] = 0
            ml_ratio[type_index] = 0
            continue
        if (usable_gold < barrel_to_buy.price) or (ml_space[type_index] < barrel_to_buy.ml_per_barrel):
            list_of_index[type_index] = list_of_index[type_index] + 1
            continue   
        buy_amt = 1
        usable_gold -= barrel_to_buy.price
        ml_space[type_index] -= barrel_to_buy.ml_per_barrel
        if barrel_to_buy not in unique_barrels:
            unique_barrels.append(barrel_to_buy)
            buy_count.append(buy_amt)
        else:
            new_quantity = buy_count[unique_barrels.index(barrel_to_buy)] + buy_amt
            if new_quantity > barrel_to_buy.quantity:
                list_of_index[type_index] += 1
                continue
            buy_count[unique_barrels.index(barrel_to_buy)] = new_quantity
        relative_change = round(barrel_to_buy.ml_per_barrel*make_int/normal) or buy_amt # Ensure ratio is updated by at least buying amount
        ml_ratio_copy[type_index] -= relative_change
        type_index = (type_index+1) % num_types 
    
    print(f"Looped {count} times")
    total_color = [0]*4
    for i in range(len(unique_barrels)):
        plan.append( {"sku":unique_barrels[i].sku, "quantity": buy_count[i]} )
        total_color[unique_barrels[i].potion_type.index(1)] += unique_barrels[i].ml_per_barrel * buy_count[i]
    print(total_color)
    print(plan)
    return plan    

if __name__ == "__main__":
    print("Ran barrels.py")
    barrel_catalog = [
            Barrel(sku='MEDIUM_RED_BARREL', ml_per_barrel=2500, potion_type=[1, 0, 0, 0], price=250, quantity=10), 
            Barrel(sku='SMALL_RED_BARREL', ml_per_barrel=500, potion_type=[1, 0, 0, 0], price=100, quantity=10), 
            Barrel(sku='MEDIUM_GREEN_BARREL', ml_per_barrel=2500, potion_type=[0, 1, 0, 0], price=250, quantity=10), 
            Barrel(sku='SMALL_GREEN_BARREL', ml_per_barrel=500, potion_type=[0, 1, 0, 0], price=100, quantity=10), 
            Barrel(sku='MEDIUM_BLUE_BARREL', ml_per_barrel=2500, potion_type=[0, 0, 1, 0], price=300, quantity=10),
            Barrel(sku='SMALL_BLUE_BARREL', ml_per_barrel=500, potion_type=[0, 0, 1, 0], price=120, quantity=10), 
            Barrel(sku='MINI_RED_BARREL', ml_per_barrel=200, potion_type=[1, 0, 0, 0], price=60, quantity=10), 
            Barrel(sku='MINI_GREEN_BARREL', ml_per_barrel=200, potion_type=[0, 1, 0, 0], price=60, quantity=10), 
            Barrel(sku='MINI_BLUE_BARREL', ml_per_barrel=200, potion_type=[0, 0, 1, 0], price=60, quantity=10), 
            Barrel(sku='LARGE_DARK_BARREL', ml_per_barrel=10000, potion_type=[0, 0, 0, 1], price=750, quantity=10), 
            Barrel(sku='LARGE_BLUE_BARREL', ml_per_barrel=10000, potion_type=[0, 0, 1, 0], price=600, quantity=30), 
            Barrel(sku='LARGE_GREEN_BARREL', ml_per_barrel=10000, potion_type=[0, 1, 0, 0], price=400, quantity=30), 
            Barrel(sku='LARGE_RED_BARREL', ml_per_barrel=10000, potion_type=[1, 0, 0, 0], price=500, quantity=30),
            Barrel(sku='LARGE_DARK_BARREL', ml_per_barrel=10000, potion_type=[0, 0, 0, 1], price=750, quantity=30)
        ]
    """
    ml_needed = [0,0,0,0]
    ml_stored = [500,500,500,0]
    usable_gold = 10500
    small_gold = 500
    ml_capacity = 10000
    """

    ml_needed = [5200,3300,2700,600]
    ml_stored = [8166,8666,5968,800]
    usable_gold = 9150
    small_gold = 500
    ml_capacity = 60000
    simplified_plan(barrel_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity)
    barrel_plan_calculation(barrel_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity)

    ml_needed = [5200,3300,2700,600]
    ml_stored = [24866,33468,33566,800]
    usable_gold = 9150
    small_gold = 500
    ml_capacity = 100000
    #simplified_plan(barrel_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity)

    ml_needed = [10280,5400,1920,4200]
    ml_stored = [37491,37218,36291,39000]
    usable_gold = 40645
    small_gold = 500
    ml_capacity = 150000
    #simplified_plan(barrel_catalog, ml_needed, ml_stored, usable_gold, small_gold, ml_capacity)
    #get_wholesale_purchase_plan(barrel_catalog)
    

