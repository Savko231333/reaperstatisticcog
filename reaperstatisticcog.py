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
    default_listener_params = {"started": "False", "channel_id": "", "role_id": "", "start_date": "", "message_logs": "True", "message_data": "True",
                               "report_channel_id": ""}
    listener_params = default_listener_params
    internal_data = {str: int}
    internal_logs = [[]]
    reaper_id = 1191502444421730385

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
            await ctx.respond("Неверный формат времени! Правильный формат ГГГГ-ММ-ДД", ephemeral=True)
            return

        self.read_logs()
        self.read_data()
        threads = []
        
        for thread in channel.threads:
            threads.append(thread)

        try:
            arcived_threads = await channel.archived_threads(limit=None).flatten()
        except discord.Forbidden as e:
            ctx.respond("Нет доступа для просмотра веток", ephemeral=True)
        except Exception as e:
            ctx.respond("Неизвестная ошибка", ephemeral=True)
        
        threads += arcived_threads

        for thread in threads:
            if thread.created_at.date() < start_date.date():
                threads.remove(thread)
                continue

            async for message in thread.history(limit=None, after=start_date).filter(lambda message: message.author in role.members):
                
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
        name="set_report_channel",
        description="Задать канал для счёта репортов"
    )
    async def set_report_channel(self, ctx: discord.ApplicationContext,
                                 channel: Option(discord.TextChannel, name="text_channel", description="Текстовый канал репортов")):
        
        if self.listener_params["report_channel_id"]:
            self.listener_params["report_channel_id"] = channel.id
            await ctx.respond("Канал репортов успешно задан", ephemeral=True)
        else:
            self.listener_params["report_channel_id"] = channel.id
            await ctx.respond("Канал репортов успешно перезаписан", ephemeral=True)

        with open(logger_params_path, "w") as params:
            params.write(json.dumps(self.listener_params))
        
    @commands.slash_command(
        name="show_reports_count",
        description="Показать количество репортов за выбранный период"
    )
    async def show_reports_count(self, ctx: discord.ApplicationContext,
                                 period: Option(str, name="period", description="Период 'ГГГГ-ММ-ДД'")):
        await ctx.defer(ephemeral=True)

        try:
            period_date = datetime.strptime(period, "%Y-%m-%d")
        except ValueError:
            await ctx.respond("Неверный формат времени! Правильный формат ГГГГ-ММ-ДД", ephemeral=True)
            return
        
        channel = discord.utils.get(ctx.guild.channels, id=self.listener_params["report_channel_id"])

        if channel is None:
            await ctx.respond("Неверный канал репортов", ephemeral=True)
            return
        
        role = discord.utils.get(ctx.guild.roles, id=self.reaper_id)

        if role is None:
            await ctx.respond("Ошибка роли", ephemeral=True)
            return
        
        punished = 0
        pardoned = 0
        veto = 0
        async for message in channel.history(limit=None, after=period_date):
            if not message.reactions:
                continue
            
            if type(message.author) is discord.user.User or role not in message.author.roles:
                continue
            
            if str(message.reactions[0]) == "⛔":
                punished += 1
                continue
            
            if str(message.reactions[0]) == "🙏":
                pardoned += 1
                continue

            if str(message.reactions[0]) == "❌":
                veto += 1
                continue

        embed = discord.Embed()
        embed.add_field(name="Наказаных", value=punished)
        embed.add_field(name="Помилованых", value=pardoned)
        embed.add_field(name="Отказаных", value=veto)
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(
    name="show_listener_messagescount",
    description="Показать кол-во сообщений участников канала"
    )
    async def show_message_count(self, ctx: discord.ApplicationContext):
        if self.listener_params['started'] == "False":
            await ctx.respond("Вы не начали слушание канала", ephemeral=True)
            return
        
        channel = discord.utils.get(ctx.guild.channels, id=self.listener_params["channel_id"])
        role = discord.utils.get(ctx.guild.roles, id=self.listener_params['role_id'])
        start_date = self.listener_params['start_date']
        
        headembed = discord.Embed(
            title=role.name,
            description=f"Кол-во сообщений каждого участника роли {role.name} в канале {channel.name} за период с {start_date} по {datetime.now().strftime("%Y-%m-%d")}",
            color=discord.Color.dark_gray() 
        )
        await ctx.defer(ephemeral=True)
        embeds = []
        embeds.append(headembed)
        self.read_data()
        
        data_items = list(self.internal_data.items())
        items = data_items
        border = 25
        s = 0
        i = 0

        while i != len(data_items):

            for key, value in items[0:25]:
                if i == len(data_items):
                    break

                member = ctx.guild.get_member(int(key))
                embeds[s].add_field(name=f"Участник {i + 1}", value=f"{member.mention} Кол-во сообщений: {value}")
                i += 1

            if i % 25 == 0:
                embeds.append(discord.Embed())
                items = data_items[border:border+25]
                border += 25
                s += 1

        for embed in embeds:
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
                self.listener_params = self.default_listener_params
                params.write(json.dumps(self.default_listener_params))

        await ctx.respond("Слушание канала и информация о пользователях удалена!", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if self.listener_params['started'] == "False":
            return
        
        if message.flags.ephemeral:
            return
        
        if message.guild is None:
            return
        
        channel = discord.utils.get(message.guild.channels, id=self.listener_params["channel_id"])

        if message.channel is not channel or channel.threads is None or message.channel not in channel.threads:
            return
        
        role = discord.utils.get(message.guild.roles, id=self.listener_params['role_id'])

        if type(message.author) is discord.user.User or role not in message.author.roles:
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
                self.internal_logs = json.loads(logs.read())
    
    def save_logs(self): 
        with open(logs_path, "w+") as logs:
            logs.write(json.dumps(self.internal_logs))

    def read_data(self):
        if os.path.exists(member_data_path):
            with open(member_data_path, "r") as data_file:
                self.internal_data = json.loads(data_file.read())
    
    def save_data(self): 
        with open(member_data_path, "w+") as data_file:
            data_file.write(json.dumps(self.internal_data))