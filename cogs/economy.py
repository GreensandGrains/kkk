import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List, Union, Literal
import json
import os
import asyncio
import datetime
import random

from utils import has_mod_permissions, has_admin_permissions

class ShopView(discord.ui.View):
    """View for the shop command with page selection"""
    
    def __init__(self, cog, user, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user = user
        self.current_page = 0
        
        # Add the page selector
        options = [
            discord.SelectOption(label="Main Menu", value="main", description="Shop main menu", emoji="🏠"),
            discord.SelectOption(label="Page 1: PokeCoin Conversion", value="1", description="Convert PokeCoins to Chari Coins", emoji="🪙"),
            discord.SelectOption(label="Page 2: Chari Coin to Real Money", value="2", description="Convert Chari Coins to INR", emoji="💰"),
            discord.SelectOption(label="Page 3: Boosters", value="3", description="XP and level boosters", emoji="🚀"),
            discord.SelectOption(label="Page 4: Minecraft", value="4", description="Minecraft game modes", emoji="⛏️"),
        ]
        
        # Add secret page option for founders/admins
        if self.cog.is_server_founder(self.user) or self.cog.is_server_admin(self.user):
            options.append(
                discord.SelectOption(label="Page 5: Secret", value="5", description="Secret Page (Admin Only)", emoji="🔒")
            )
        
        self.add_item(PageSelector(options))
    
    async def show_page(self, interaction: discord.Interaction, page_num: Union[int, str]):
        """Show the specified page of the shop"""
        self.current_page = page_num
        
        if page_num == "main":
            embed = self.cog.get_shop_main_page()
        else:
            embed = self.cog.get_shop_page(int(page_num))
        
        await interaction.response.edit_message(embed=embed, view=self)

class PageSelector(discord.ui.Select):
    """Dropdown for selecting shop pages"""
    
    def __init__(self, options):
        super().__init__(
            placeholder="Select a shop page...",
            options=options,
            custom_id="shop_page_selector"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle page selection"""
        # Only allow the original user to use this
        if interaction.user.id != self.view.user.id:
            await interaction.response.send_message("This isn't your shop menu!", ephemeral=True)
            return
        
        selected_page = self.values[0]
        await self.view.show_page(interaction, selected_page)

class TradeButton(discord.ui.Button):
    """Button for accepting trades"""
    
    def __init__(self, trade_id, label="Accept Trade", style=discord.ButtonStyle.green):
        super().__init__(style=style, label=label, custom_id=f"trade_accept_{trade_id}")
        self.trade_id = trade_id
    
    async def callback(self, interaction: discord.Interaction):
        """Handle trade acceptance"""
        # Get the cog
        economy_cog = interaction.client.get_cog("Economy")
        if not economy_cog:
            await interaction.response.send_message("Economy system is not currently loaded.", ephemeral=True)
            return
        
        # Process the trade
        await economy_cog.accept_trade(interaction, self.trade_id)

class Economy(commands.Cog):
    """Economy system with coins, inventory, shop, and trading"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "data/economy.json"
        self.ensure_data_file()
        self.economy_data = self.load_data()
        self.pending_trades = {}
        
        # Shop items configuration
        self.shop_items = {
            1: {  # PokeCoin Conversion
                "title": "PokeCoin Conversion",
                "emoji": "🪙",
                "description": "Convert your PokeCoins to Chari Coins",
                "items": [
                    {"name": "2,000 PokeCoins", "price": 1000, "description": "Convert 2,000 PokeCoins to 1,000 Chari Coins", "id": "convert_2k"},
                    {"name": "5,000 PokeCoins", "price": 2500, "description": "Convert 5,000 PokeCoins to 2,500 Chari Coins", "id": "convert_5k"},
                    {"name": "10,000 PokeCoins", "price": 5000, "description": "Convert 10,000 PokeCoins to 5,000 Chari Coins", "id": "convert_10k"}
                ]
            },
            2: {  # Chari Coin to Real Money
                "title": "Chari Coin to Real Money",
                "emoji": "💰",
                "description": "Convert your Chari Coins to INR",
                "items": [
                    {"name": "10,000 Chari Coins", "price": 10000, "description": "Convert to 5 INR", "id": "money_10k"},
                    {"name": "20,000 Chari Coins", "price": 20000, "description": "Convert to 10 INR", "id": "money_20k"},
                    {"name": "50,000 Chari Coins", "price": 50000, "description": "Convert to 25 INR", "id": "money_50k"},
                    {"name": "100,000 Chari Coins", "price": 100000, "description": "Convert to 50 INR", "id": "money_100k"}
                ]
            },
            3: {  # Boosters
                "title": "XP & Level Boosters",
                "emoji": "🚀",
                "description": "Boost your XP gain and level up faster",
                "items": [
                    {"name": "2.5x XP Booster", "price": 10000, "description": "2.5x XP gain for 24 hours", "id": "boost_2.5x"},
                    {"name": "5x XP Booster", "price": 50000, "description": "5x XP gain for 24 hours", "id": "boost_5x"},
                    {"name": "Instant Level Up", "price": 70000, "description": "Instantly gain one level", "id": "instant_level"}
                ]
            },
            4: {  # Minecraft
                "title": "Minecraft Games",
                "emoji": "⛏️",
                "description": "Purchase access to Minecraft game modes\n**Note:** Server hosting not included",
                "items": [
                    {"name": "Survival Mode", "price": 10000, "description": "Access to Survival game mode", "id": "mc_survival"},
                    {"name": "Bed Wars", "price": 30000, "description": "Access to Bed Wars game mode", "id": "mc_bedwars"},
                    {"name": "Sky Wars", "price": 30000, "description": "Access to Sky Wars game mode", "id": "mc_skywars"},
                    {"name": "OneBlock", "price": 30000, "description": "Access to OneBlock game mode", "id": "mc_oneblock"},
                    {"name": "Duel", "price": 30000, "description": "Access to Duel game mode", "id": "mc_duel"},
                    {"name": "Life Steal", "price": 30000, "description": "Access to Life Steal game mode", "id": "mc_lifesteal"}
                ]
            },
            5: {  # Secret page (admin/founder only)
                "title": "Secret Page",
                "emoji": "🔒",
                "description": "Special content for administrators and founders",
                "items": [
                    {"name": "ArchXBot Website", "price": 0, "description": "Access to the official ArchXBot website", "id": "archx_website", "url": "https://greensandgrains.github.io/ArchXBot/"}
                ]
            }
        }

    def ensure_data_file(self):
        """Ensure the economy data file exists"""
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump({"users": {}, "transactions": []}, f)
    
    def load_data(self):
        """Load economy data from file"""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"users": {}, "transactions": []}
    
    def save_data(self):
        """Save economy data to file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.economy_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving economy data: {e}")
            return False
    
    def get_user_data(self, user_id: int):
        """Get a user's economy data"""
        user_id = str(user_id)
        if user_id not in self.economy_data["users"]:
            # Initialize new user
            self.economy_data["users"][user_id] = {
                "balance": 0,
                "inventory": {},
                "last_daily": None,
                "transactions": []
            }
            self.save_data()
        
        return self.economy_data["users"][user_id]
    
    def get_balance(self, user_id: int):
        """Get a user's balance"""
        user_data = self.get_user_data(user_id)
        return user_data.get("balance", 0)
    
    def add_coins(self, user_id: int, amount: int, reason: str = "System transfer"):
        """Add coins to a user's balance"""
        if amount <= 0:
            return False
        
        user_data = self.get_user_data(user_id)
        user_data["balance"] += amount
        
        # Record transaction
        transaction = {
            "type": "add",
            "amount": amount,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "reason": reason
        }
        user_data["transactions"].append(transaction)
        
        self.save_data()
        return True
    
    def remove_coins(self, user_id: int, amount: int, reason: str = "System deduction"):
        """Remove coins from a user's balance"""
        if amount <= 0:
            return False
        
        user_data = self.get_user_data(user_id)
        if user_data["balance"] < amount:
            return False
        
        user_data["balance"] -= amount
        
        # Record transaction
        transaction = {
            "type": "remove",
            "amount": amount,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "reason": reason
        }
        user_data["transactions"].append(transaction)
        
        self.save_data()
        return True
    
    def add_item_to_inventory(self, user_id: int, item_id: str, quantity: int = 1):
        """Add an item to a user's inventory"""
        user_data = self.get_user_data(user_id)
        
        if "inventory" not in user_data:
            user_data["inventory"] = {}
        
        if item_id not in user_data["inventory"]:
            user_data["inventory"][item_id] = 0
        
        user_data["inventory"][item_id] += quantity
        self.save_data()
        return True
    
    def remove_item_from_inventory(self, user_id: int, item_id: str, quantity: int = 1):
        """Remove an item from a user's inventory"""
        user_data = self.get_user_data(user_id)
        
        if "inventory" not in user_data or item_id not in user_data["inventory"]:
            return False
        
        if user_data["inventory"][item_id] < quantity:
            return False
        
        user_data["inventory"][item_id] -= quantity
        
        # Remove item from inventory if quantity is 0
        if user_data["inventory"][item_id] <= 0:
            del user_data["inventory"][item_id]
        
        self.save_data()
        return True
    
    def is_server_founder(self, user: discord.Member):
        """Check if a user is the founder of their server"""
        return user.id == user.guild.owner_id
    
    def is_server_admin(self, user: discord.Member):
        """Check if a user is an admin in their server"""
        # Check for Administrator permission
        if user.guild_permissions.administrator:
            return True
        
        # Check for admin roles
        for role in user.roles:
            if role.permissions.administrator:
                return True
        
        return False
    
    def get_shop_main_page(self):
        """Get the main shop page embed"""
        embed = discord.Embed(
            title="🛒 Chari Shop",
            description="Welcome to the Chari Shop! Use the dropdown menu below to navigate.",
            color=discord.Color.gold()
        )
        
        # Add all shop categories
        for page_num, page_data in self.shop_items.items():
            if page_num == 5:  # Skip secret page in the main listing
                continue
                
            embed.add_field(
                name=f"{page_data['emoji']} Page {page_num}: {page_data['title']}",
                value=page_data['description'],
                inline=False
            )
        
        embed.set_footer(text="Select a page from the dropdown menu below")
        return embed
    
    def get_shop_page(self, page_num: int):
        """Get a specific shop page embed"""
        if page_num not in self.shop_items:
            return discord.Embed(
                title="❌ Invalid Page",
                description="This shop page does not exist.",
                color=discord.Color.red()
            )
        
        page_data = self.shop_items[page_num]
        
        embed = discord.Embed(
            title=f"{page_data['emoji']} {page_data['title']}",
            description=page_data['description'],
            color=discord.Color.gold()
        )
        
        # Add all items in this category
        for item in page_data['items']:
            if 'url' in item:
                value = f"{item['description']}\n**Price:** {item['price']} Chari Coins\n[Click Here]({item['url']})"
            else:
                value = f"{item['description']}\n**Price:** {item['price']} Chari Coins\n*Use `/buy {item['id']}` to purchase*"
                
            embed.add_field(
                name=item['name'],
                value=value,
                inline=True
            )
        
        embed.set_footer(text="Use the dropdown menu to navigate the shop")
        return embed
    
    def get_item_by_id(self, item_id: str):
        """Get an item by its ID"""
        for page_data in self.shop_items.values():
            for item in page_data['items']:
                if item['id'] == item_id:
                    return item
        return None
    
    @app_commands.command(name="balance", description="Check your Chari Coin balance")
    @app_commands.describe(
        user="The user to check the balance for (defaults to yourself)"
    )
    async def balance_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None
    ):
        # Use command invoker if no user is specified
        target_user = user or interaction.user
        
        # Get balance
        balance = self.get_balance(target_user.id)
        
        # Create embed
        embed = discord.Embed(
            title=f"{target_user.display_name}'s Balance",
            description=f"**{balance:,}** Chari Coins 🪙",
            color=discord.Color.gold()
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Only show to the user if checking someone else's balance
        ephemeral = user is not None and user.id != interaction.user.id
        
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    
    @app_commands.command(name="inventory", description="Check your inventory")
    @app_commands.describe(
        user="The user to check the inventory for (defaults to yourself)"
    )
    async def inventory_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None
    ):
        # Use command invoker if no user is specified
        target_user = user or interaction.user
        
        # Get user data
        user_data = self.get_user_data(target_user.id)
        inventory = user_data.get("inventory", {})
        
        if not inventory:
            await interaction.response.send_message(
                f"{target_user.mention} doesn't have any items in their inventory.",
                ephemeral=True
            )
            return
        
        # Create inventory embed
        embed = discord.Embed(
            title=f"{target_user.display_name}'s Inventory",
            description=f"Items owned by {target_user.mention}",
            color=discord.Color.blue()
        )
        
        # Group items by type/category
        grouped_items = {}
        
        for item_id, quantity in inventory.items():
            item = self.get_item_by_id(item_id)
            if item:
                category = next((page_data["title"] for page_num, page_data in self.shop_items.items() 
                               if any(i["id"] == item_id for i in page_data["items"])), "Miscellaneous")
                
                if category not in grouped_items:
                    grouped_items[category] = []
                
                grouped_items[category].append(f"**{item['name']}** x{quantity}")
            else:
                # Handle unknown items
                if "Miscellaneous" not in grouped_items:
                    grouped_items["Miscellaneous"] = []
                
                grouped_items["Miscellaneous"].append(f"**{item_id}** x{quantity}")
        
        # Add item groups to embed
        for category, items in grouped_items.items():
            embed.add_field(
                name=category,
                value="\n".join(items),
                inline=False
            )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Only show to the user if checking someone else's inventory
        ephemeral = user is not None and user.id != interaction.user.id
        
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    
    @app_commands.command(name="shop", description="Browse the Chari Coins shop")
    async def shop_command(
        self, 
        interaction: discord.Interaction,
        page: Optional[int] = None
    ):
        # Show main page or specific page
        if page is not None and (page < 1 or page > 5 or (page == 5 and not (self.is_server_founder(interaction.user) or self.is_server_admin(interaction.user)))):
            await interaction.response.send_message(
                "Invalid shop page number. Please select a page between 1 and 4.",
                ephemeral=True
            )
            return
        
        # Create shop view
        view = ShopView(self, interaction.user)
        
        # Get the appropriate embed
        if page is None:
            embed = self.get_shop_main_page()
            view.current_page = "main"
        else:
            embed = self.get_shop_page(page)
            view.current_page = page
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="buy", description="Buy an item from the shop")
    @app_commands.describe(
        item_id="The ID of the item to buy"
    )
    async def buy_command(
        self, 
        interaction: discord.Interaction, 
        item_id: str
    ):
        # Find the item
        item = self.get_item_by_id(item_id)
        
        if not item:
            await interaction.response.send_message(
                f"Item with ID '{item_id}' does not exist in the shop.",
                ephemeral=True
            )
            return
        
        # Check if user has enough coins
        balance = self.get_balance(interaction.user.id)
        
        if balance < item["price"]:
            await interaction.response.send_message(
                f"You don't have enough Chari Coins! The item costs {item['price']} coins, but you only have {balance}.",
                ephemeral=True
            )
            return
        
        # Process purchase
        success = self.remove_coins(
            interaction.user.id,
            item["price"],
            f"Purchased {item['name']}"
        )
        
        if not success:
            await interaction.response.send_message(
                "Failed to process the purchase. Please try again.",
                ephemeral=True
            )
            return
        
        # Add item to inventory
        self.add_item_to_inventory(interaction.user.id, item_id)
        
        # Create purchase confirmation
        embed = discord.Embed(
            title="Purchase Successful",
            description=f"You have purchased **{item['name']}**!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Price",
            value=f"{item['price']} Chari Coins",
            inline=True
        )
        
        embed.add_field(
            name="New Balance",
            value=f"{balance - item['price']} Chari Coins",
            inline=True
        )
        
        embed.set_footer(text="Use /inventory to view your items")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="daily", description="Claim your daily Chari Coins")
    async def daily_command(self, interaction: discord.Interaction):
        user_data = self.get_user_data(interaction.user.id)
        
        # Check if already claimed today
        last_daily = user_data.get("last_daily")
        
        if last_daily:
            last_claim_time = datetime.datetime.fromisoformat(last_daily)
            now = datetime.datetime.utcnow()
            time_since_last = now - last_claim_time
            
            if time_since_last.total_seconds() < 86400:  # 24 hours in seconds
                next_claim = last_claim_time + datetime.timedelta(days=1)
                time_until_next = next_claim - now
                hours, remainder = divmod(int(time_until_next.total_seconds()), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                await interaction.response.send_message(
                    f"You've already claimed your daily reward! You can claim again in **{hours}h {minutes}m {seconds}s**.",
                    ephemeral=True
                )
                return
        
        # Calculate reward (base amount + streak bonus)
        streak = user_data.get("daily_streak", 0)
        
        if last_daily:
            last_claim_time = datetime.datetime.fromisoformat(last_daily)
            now = datetime.datetime.utcnow()
            
            # If last claim was yesterday, increase streak
            if (now - last_claim_time).total_seconds() < 172800:  # 48 hours
                streak += 1
            else:
                streak = 1
        else:
            streak = 1
        
        user_data["daily_streak"] = streak
        
        # Base reward + streak bonus (max 500)
        base_reward = 500
        streak_bonus = min(streak * 50, 500)
        total_reward = base_reward + streak_bonus
        
        # Add coins
        self.add_coins(
            interaction.user.id,
            total_reward,
            "Daily reward"
        )
        
        # Update last claim time
        user_data["last_daily"] = datetime.datetime.utcnow().isoformat()
        self.save_data()
        
        # Create reward message
        embed = discord.Embed(
            title="Daily Reward Claimed",
            description=f"You received **{total_reward}** Chari Coins! 🪙",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Streak",
            value=f"{streak} day{'s' if streak > 1 else ''}",
            inline=True
        )
        
        if streak_bonus > 0:
            embed.add_field(
                name="Streak Bonus",
                value=f"+{streak_bonus} coins",
                inline=True
            )
        
        embed.add_field(
            name="New Balance",
            value=f"{self.get_balance(interaction.user.id)} Chari Coins",
            inline=True
        )
        
        embed.set_footer(text="Come back tomorrow for another reward!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="give", description="Give Chari Coins to another user")
    @app_commands.describe(
        user="The user to give coins to",
        amount="Amount of coins to give"
    )
    async def give_command(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        amount: int
    ):
        # Check if trying to give to self
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't give coins to yourself!",
                ephemeral=True
            )
            return
        
        # Validate amount
        if amount <= 0:
            await interaction.response.send_message(
                "You must give a positive amount of coins.",
                ephemeral=True
            )
            return
        
        # Check if user has enough coins
        balance = self.get_balance(interaction.user.id)
        
        if balance < amount:
            await interaction.response.send_message(
                f"You don't have enough coins! You're trying to give {amount} coins, but you only have {balance}.",
                ephemeral=True
            )
            return
        
        # Transfer coins
        self.remove_coins(
            interaction.user.id,
            amount,
            f"Gift to {user.display_name}"
        )
        
        self.add_coins(
            user.id,
            amount,
            f"Gift from {interaction.user.display_name}"
        )
        
        # Create confirmation message
        embed = discord.Embed(
            title="Coins Transferred",
            description=f"You gave **{amount}** Chari Coins to {user.mention}!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Your New Balance",
            value=f"{balance - amount} Chari Coins",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Notify the recipient
        try:
            recipient_embed = discord.Embed(
                title="You Received Coins!",
                description=f"You received **{amount}** Chari Coins from {interaction.user.mention}!",
                color=discord.Color.green()
            )
            
            recipient_embed.add_field(
                name="Your New Balance",
                value=f"{self.get_balance(user.id)} Chari Coins",
                inline=True
            )
            
            await user.send(embed=recipient_embed)
        except discord.HTTPException:
            # Couldn't DM the user, ignore
            pass
    
    @app_commands.command(name="addcoins", description="Add Chari Coins to a user (Admin only)")
    @app_commands.describe(
        user="The user to add coins to",
        amount="Amount of coins to add"
    )
    async def addcoins_command(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        amount: int
    ):
        # Check permissions
        if not (self.is_server_founder(interaction.user) or self.is_server_admin(interaction.user)):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        # Validate amount
        if amount <= 0:
            await interaction.response.send_message(
                "You must add a positive amount of coins.",
                ephemeral=True
            )
            return
        
        # Add coins
        self.add_coins(
            user.id,
            amount,
            f"Admin gift from {interaction.user.display_name}"
        )
        
        # Create confirmation message
        embed = discord.Embed(
            title="Coins Added",
            description=f"You added **{amount}** Chari Coins to {user.mention}!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Their New Balance",
            value=f"{self.get_balance(user.id)} Chari Coins",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="removecoins", description="Remove Chari Coins from a user (Admin only)")
    @app_commands.describe(
        user="The user to remove coins from",
        amount="Amount of coins to remove"
    )
    async def removecoins_command(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        amount: int
    ):
        # Check permissions
        if not (self.is_server_founder(interaction.user) or self.is_server_admin(interaction.user)):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
        
        # Validate amount
        if amount <= 0:
            await interaction.response.send_message(
                "You must remove a positive amount of coins.",
                ephemeral=True
            )
            return
        
        # Check if user has enough coins
        balance = self.get_balance(user.id)
        
        if balance < amount:
            await interaction.response.send_message(
                f"{user.mention} only has {balance} Chari Coins, but you're trying to remove {amount}.",
                ephemeral=True
            )
            return
        
        # Remove coins
        self.remove_coins(
            user.id,
            amount,
            f"Admin deduction by {interaction.user.display_name}"
        )
        
        # Create confirmation message
        embed = discord.Embed(
            title="Coins Removed",
            description=f"You removed **{amount}** Chari Coins from {user.mention}!",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="Their New Balance",
            value=f"{self.get_balance(user.id)} Chari Coins",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="trade", description="Trade items or coins with another user")
    @app_commands.describe(
        user="The user to trade with",
        your_coins="Amount of coins you're offering (0 for none)",
        item_id="ID of item you're offering (leave empty for none)"
    )
    async def trade_command(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        your_coins: Optional[int] = 0,
        item_id: Optional[str] = None
    ):
        # Check if trying to trade with self
        if user.id == interaction.user.id:
            await interaction.response.send_message(
                "You can't trade with yourself!",
                ephemeral=True
            )
            return
        
        # Validate trade
        if your_coins <= 0 and not item_id:
            await interaction.response.send_message(
                "You must offer either coins or an item for the trade.",
                ephemeral=True
            )
            return
        
        # Check if has enough coins
        if your_coins > 0:
            balance = self.get_balance(interaction.user.id)
            
            if balance < your_coins:
                await interaction.response.send_message(
                    f"You don't have enough coins! You're offering {your_coins} coins, but you only have {balance}.",
                    ephemeral=True
                )
                return
        
        # Check if has the item
        if item_id:
            user_data = self.get_user_data(interaction.user.id)
            inventory = user_data.get("inventory", {})
            
            if item_id not in inventory or inventory[item_id] <= 0:
                await interaction.response.send_message(
                    f"You don't have the item '{item_id}' in your inventory.",
                    ephemeral=True
                )
                return
        
        # Generate trade ID
        trade_id = f"{interaction.user.id}_{user.id}_{int(datetime.datetime.utcnow().timestamp())}"
        
        # Store trade info
        self.pending_trades[trade_id] = {
            "initiator_id": interaction.user.id,
            "target_id": user.id,
            "coins": your_coins,
            "item_id": item_id,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Create trade offer message
        embed = discord.Embed(
            title="Trade Offer",
            description=f"{interaction.user.mention} wants to trade with you!",
            color=discord.Color.blue()
        )
        
        # Add offer details
        offer_text = ""
        if your_coins > 0:
            offer_text += f"**{your_coins}** Chari Coins\n"
        
        if item_id:
            item = self.get_item_by_id(item_id)
            if item:
                offer_text += f"**{item['name']}**"
            else:
                offer_text += f"**{item_id}**"
        
        embed.add_field(
            name="They're offering:",
            value=offer_text,
            inline=False
        )
        
        embed.add_field(
            name="To accept this trade:",
            value="Click the button below",
            inline=False
        )
        
        embed.set_footer(text=f"Trade ID: {trade_id}")
        
        # Create view with accept button
        view = discord.ui.View()
        view.add_item(TradeButton(trade_id))
        
        try:
            await user.send(embed=embed, view=view)
            
            # Let the initiator know the offer was sent
            await interaction.response.send_message(
                f"Trade offer sent to {user.mention}! They'll need to accept the trade to complete it.",
                ephemeral=True
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                f"Failed to send trade offer to {user.mention}. They might have DMs disabled.",
                ephemeral=True
            )
    
    async def accept_trade(self, interaction: discord.Interaction, trade_id: str):
        """Process a trade acceptance"""
        # Check if trade exists
        if trade_id not in self.pending_trades:
            await interaction.response.send_message(
                "This trade is no longer valid.",
                ephemeral=True
            )
            return
        
        trade_info = self.pending_trades[trade_id]
        
        # Check if user is the target
        if interaction.user.id != trade_info["target_id"]:
            await interaction.response.send_message(
                "This trade offer is not for you.",
                ephemeral=True
            )
            return
        
        # Get users
        initiator = self.bot.get_user(trade_info["initiator_id"])
        if not initiator:
            await interaction.response.send_message(
                "The trade initiator is no longer available.",
                ephemeral=True
            )
            return
        
        # Check if initiator still has coins/items
        has_resources = True
        error_message = ""
        
        if trade_info["coins"] > 0:
            initiator_balance = self.get_balance(initiator.id)
            if initiator_balance < trade_info["coins"]:
                has_resources = False
                error_message = f"{initiator.mention} no longer has enough coins for this trade."
        
        if trade_info["item_id"]:
            initiator_data = self.get_user_data(initiator.id)
            initiator_inventory = initiator_data.get("inventory", {})
            
            if trade_info["item_id"] not in initiator_inventory or initiator_inventory[trade_info["item_id"]] <= 0:
                has_resources = False
                error_message = f"{initiator.mention} no longer has the item for this trade."
        
        if not has_resources:
            await interaction.response.send_message(error_message, ephemeral=True)
            del self.pending_trades[trade_id]
            return
        
        # Process the trade
        success = True
        
        if trade_info["coins"] > 0:
            success = self.remove_coins(
                initiator.id,
                trade_info["coins"],
                f"Trade with {interaction.user.display_name}"
            )
            
            if success:
                self.add_coins(
                    interaction.user.id,
                    trade_info["coins"],
                    f"Trade with {initiator.display_name}"
                )
        
        if success and trade_info["item_id"]:
            success = self.remove_item_from_inventory(initiator.id, trade_info["item_id"])
            
            if success:
                self.add_item_to_inventory(interaction.user.id, trade_info["item_id"])
        
        if not success:
            await interaction.response.send_message(
                "Failed to process the trade due to an error. Please try again.",
                ephemeral=True
            )
            return
        
        # Create confirmation for both users
        embed = discord.Embed(
            title="Trade Completed",
            description=f"Trade between {initiator.mention} and {interaction.user.mention} was successful!",
            color=discord.Color.green()
        )
        
        # Add traded items/coins
        offer_text = ""
        if trade_info["coins"] > 0:
            offer_text += f"**{trade_info['coins']}** Chari Coins\n"
        
        if trade_info["item_id"]:
            item = self.get_item_by_id(trade_info["item_id"])
            if item:
                offer_text += f"**{item['name']}**"
            else:
                offer_text += f"**{trade_info['item_id']}**"
        
        embed.add_field(
            name=f"{initiator.display_name} gave:",
            value=offer_text,
            inline=False
        )
        
        # Send confirmation to both users
        await interaction.response.send_message(embed=embed)
        
        try:
            await initiator.send(embed=embed)
        except discord.HTTPException:
            # Couldn't DM initiator, ignore
            pass
        
        # Remove the trade from pending
        del self.pending_trades[trade_id]

async def setup(bot):
    await bot.add_cog(Economy(bot))