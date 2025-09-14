import discord
from discord.ext import commands
from discord import Option

import os
import json
from datetime import datetime

member_data_path = os.path.join(os.path.dirname(__file__), "member_data.json")
logger_params_path = os.path.join(os.path.dirname(__file__), "logger_params.json")
logs_path = os.path.join(os.path.dirname(__file__), "logs.json")
class ReaperStatisticCog(commands.Cog):
    default_listener_params = {"started": "False", "channel_id": "", "role_id": "", "start_date": "", "message_logs": "True", "message_data": "True"}
    listener_params = default_listener_params
    internal_data = {str: int}
    internal_logs = [[]]
    @commands.Cog.listener()
    async def on_ready(self):

        if os.path.exists(logger_params_path):
            with open(logger_params_path, "r") as params:
                listener_params = json.loads(params.read())
                self.listener_params = listener_params
        else:
            with open(logger_params_path, "w") as params:
                params.write(json.dumps(self.default_listener_params))

    @commands.slash_command(
    name='start_listener',
    description='Начало счёта сообщений и информации о пользователях в конкретном канале' 
    )
    async def start_listener(self, 
                           ctx: discord.ApplicationContext, 
                           role: Option(discord.Role, name="role", description="Роль для логирования"), 
                           channel: Option(discord.TextChannel, name="text_channel", description="Текстовый канал для логирования"),
                           start_date_str: Option(str, name="start_date", description="Время для начала логирования в формате 'ГГГГ-ММ-ДД'")):
        await ctx.defer(ephemeral=True)

        if self.listener_params["started"] == "True":
            await ctx.respond("История уже была записана", ephemeral=True)
            return
        
        self.listener_params['channel_id'] = channel.id
        self.listener_params['role_id'] = role.id
        self.listener_params['start_date'] = start_date_str
            
        self.internal_data.clear()
        self.internal_logs.clear()
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            await ctx.respond("Неверный формат времени!", ephemeral=True)
        self.read_logs()
        self.read_data()


        async for message in channel.history(limit=None, after=start_date):
            if message.author not in role.members:
                continue

            if self.listener_params['message_logs'] == "True":
                log = [message.author.name, str(message.created_at)]
                self.internal_logs.append(log)

            if self.listener_params["message_data"] == "True":
                if self.internal_data.get(str(message.author.id), False):
                    self.internal_data[str(message.author.id)] += 1
                else:
                    self.internal_data[str(message.author.id)] = 1

        self.save_logs()
        self.save_data()

        self.listener_params['started'] = "True"
        with open(logger_params_path, "w") as params:
            params.write(json.dumps(self.listener_params))

        await ctx.respond(f"История записана! Логирование: {self.listener_params['message_logs']}. Данные пользователей: {self.listener_params["message_data"]}", ephemeral=True)


    @commands.slash_command(
    name="show_listener_messagescount",
    description="Показать кол-во сообщений участников канала"
    )
    async def show_message_count(self, ctx: discord.ApplicationContext):
        if self.listener_params['started'] == "False":
            await ctx.respond("Вы не начали слушание канала")
            return
        
        channel = discord.utils.get(ctx.guild.channels, id=self.listener_params["channel_id"])
        role = discord.utils.get(ctx.guild.roles, id=self.listener_params['role_id'])
        start_date = self.listener_params['start_date']
        embed = discord.Embed(
            title=role.name,
            description=f"Кол-во сообщений каждого участника роли {role.name} в канале {channel.name} за период с {start_date} по {datetime.now().strftime("%Y-%m-%d")}",
            color=discord.Color.dark_gray() 
        )
        await ctx.defer(ephemeral=True)

        self.read_data()

        i = 1
        for member in role.members:
            embed.add_field(name=f"Участник {i}", value=f"{member.mention} Кол-во сообщений: {self.internal_data[str(member.id)]}")
            i += 1

        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(
    name="delete_listener",
    description="Удалить информацию о пользователях и закончить их счёт"
    )
    async def delete_listener(self, ctx: discord.ApplicationContext):
        if self.listener_params['started'] == "False":
            await ctx.respond("Вы не начали слушание канала", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)

        if os.path.exists(logs_path):
            os.remove(logs_path)
        if os.path.exists(member_data_path):
            os.remove(member_data_path)
        if os.path.exists(logger_params_path):
            with open(logger_params_path, "w+") as params:
                params.write(json.dumps(self.default_listener_params))
                self.listener_params = self.default_listener_params

        await ctx.respond("Слушание канала и информация о пользователях удалена!", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if self.listener_params['started'] == "False":
            return
        
        if message.flags.ephemeral:
            return

        channel = discord.utils.get(message.guild.channels, id=self.listener_params["channel_id"])
        
        if message.channel is not channel:
            return
        
        role = discord.utils.get(message.guild.roles, id=self.listener_params['role_id'])

        if message.author is discord.User or role not in message.author.roles:
            return
        
        self.read_logs()
        self.read_data()

        if self.listener_params['message_logs'] == "True":
            log = [message.author.name, str(message.created_at)]
            self.internal_logs.append(log)

        if self.listener_params['message_data'] == "True":
            if self.internal_data.get(str(message.author.id), False):
                self.internal_data[str(message.author.id)] += 1
            else:
                self.internal_data[str(message.author.id)] = 1

        self.save_logs()
        self.save_data()

    def read_logs(self):
        if os.path.exists(logs_path):
            with open(logs_path, "r") as logs:
                temp: list[list] = json.loads(logs.read())
                self.internal_logs = temp
    
    def save_logs(self): 
        with open(logs_path, "w+") as logs:
            logs.write(json.dumps(self.internal_logs))

    def read_data(self):
        if os.path.exists(member_data_path):
            with open(member_data_path, "r") as data_file:
                temp = json.loads(data_file.read())
                self.internal_data = temp
    
    def save_data(self): 
        with open(member_data_path, "w+") as data_file:
            data_file.write(json.dumps(self.internal_data))
