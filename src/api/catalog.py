from fastapi import APIRouter

import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    potions_available = []
    with db.engine.begin() as connection: 
        sql_to_execute = """SELECT sku, quantity, price, red, green, blue, dark, name FROM potions ORDER BY quantity DESC LIMIT 6"""
        potions = connection.execute(sqlalchemy.text(sql_to_execute))
        for potion in potions:
            if potion.quantity > 0:
                potions_available.append( {
                    "sku": potion.sku,
                    "name": potion.name,
                    "quantity": potion.quantity,
                    "price": int(potion.price),
                    "potion_type": [potion.red, potion.green, potion.blue, potion.dark]
                } )
    print(potions_available)
    return potions_available
