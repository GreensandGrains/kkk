"""
Utility functions for checking permissions.
"""
import discord
from discord.ext import commands
from typing import Union, Optional

class PermissionManager:
    """Manages permission checks for commands."""
    
    @staticmethod
    async def check_mod_roles(ctx, bot) -> bool:
        """Check if user has a moderator role or admin permissions."""
        # Admin override
        if ctx.author.guild_permissions.administrator:
            return True
        
        # Get mod roles from config
        from utils.db import Database
        config = Database.get_config(ctx.guild.id)
        
        mod_roles = config.get('mod_roles', [])
        if not mod_roles:
            return False
        
        # Check if user has any mod role
        return any(role.id in mod_roles for role in ctx.author.roles)
    
    @staticmethod
    async def check_admin_roles(ctx, bot) -> bool:
        """Check if user has an admin role or admin permissions."""
        # Admin override
        if ctx.author.guild_permissions.administrator:
            return True
        
        # Get admin roles from config
        from utils.db import Database
        config = Database.get_config(ctx.guild.id)
        
        admin_roles = config.get('admin_roles', [])
        if not admin_roles:
            return False
        
        # Check if user has any admin role
        return any(role.id in admin_roles for role in ctx.author.roles)
    
    @staticmethod
    def mod_or_permissions(**perms):
        """A decorator to check if user has mod role or specific permissions."""
        async def predicate(ctx):
            if await PermissionManager.check_mod_roles(ctx, ctx.bot):
                return True
            
            # Check for the permissions if not a mod
            permissions = ctx.channel.permissions_for(ctx.author)
            return all(getattr(permissions, perm, None) for perm in perms)
        
        return commands.check(predicate)
    
    @staticmethod
    def admin_or_permissions(**perms):
        """A decorator to check if user has admin role or specific permissions."""
        async def predicate(ctx):
            if await PermissionManager.check_admin_roles(ctx, ctx.bot):
                return True
            
            # Check for the permissions if not an admin
            permissions = ctx.channel.permissions_for(ctx.author)
            return all(getattr(permissions, perm, None) for perm in perms)
        
        return commands.check(predicate)
    
    @staticmethod
    def check_hierarchy(user: discord.Member, target: discord.Member) -> bool:
        """Check if user is higher in role hierarchy than target."""
        return user.top_role > target.top_role
    
    @staticmethod
    def can_moderate(ctx, target: discord.Member, bot_member: discord.Member) -> tuple:
        """
        Check if a user can moderate a target.
        
        Returns:
            tuple: (can_moderate, reason)
        """
        # Check if target is the bot itself
        if target.id == bot_member.id:
            return False, "I cannot moderate myself."
        
        # Check if target is the guild owner
        if target.id == ctx.guild.owner_id:
            return False, "I cannot moderate the server owner."
        
        # Check if user is trying to moderate themselves
        if target.id == ctx.author.id:
            return False, "You cannot moderate yourself."
        
        # Check target's roles vs bot's roles
        if not PermissionManager.check_hierarchy(bot_member, target):
            return False, "I don't have permission to moderate this user due to role hierarchy."
        
        # Check user's roles vs target's roles
        if not PermissionManager.check_hierarchy(ctx.author, target):
            return False, "You don't have permission to moderate this user due to role hierarchy."
        
        return True, None
