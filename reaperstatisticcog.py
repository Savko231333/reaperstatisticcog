import discord
from discord.ext import commands
from discord import Option

import os
import json
import shutil
from datetime import datetime

member_data_path = os.path.join(os.path.dirname(__file__), "member_data.json")
logger_params_path = os.path.join(os.path.dirname(__file__), "logger_params.json")
logs_path = os.path.join(os.path.dirname(__file__), "logs")
class ReaperStatisticCog(commands.Cog):
    default_listener_params = {"started": "False", "channel_id": "", "role_id": "", "start_date": "", "message_logs": "True"}
    listener_params = default_listener_params
    internal_data = [[]]

    @commands.Cog.listener()
    async def on_ready(self):
        if not os.path.exists(logs_path):
            os.mkdir(logs_path)

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
        await ctx.defer()

        if self.listener_params["started"] == "True":
            await ctx.followup.send("История уже была записана")
            return
        
        self.listener_params['channel_id'] = channel.id
        self.listener_params['role_id'] = role.id
        self.listener_params['start_date'] = start_date_str
            
        self.internal_data.clear()

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        for member in role.members:
            i = 0
            async for message in channel.history(limit=None):
                if message.created_at.date() <= start_date:
                    break

                if message.author.id != member.id:
                    continue

                if self.listener_params['message_logs'] == "True":
                    message_logs_path = self.create_message_logs_path(message)
                    self.write_logs(message_logs_path, str(message.created_at), member.name)

                i += 1

            if i != 0:
                data = [member.display_name, str(i)]
                self.internal_data.append(data)
                with open(member_data_path, "w+") as data_file:
                    data_file.write(json.dumps(self.internal_data))
                with open(member_data_path, "r") as data_file:
                    self.internal_data = json.loads(data_file.read())

        self.listener_params['started'] = "True"
        with open(logger_params_path, "w") as params:
            params.write(json.dumps(self.listener_params))

        await ctx.followup.send(f"История записана! Логирование: {self.listener_params['message_logs']}", ephemeral=True)


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
        await ctx.defer()

        with open(member_data_path, "r") as data:
            data_list: list[list] = json.loads(data.read())
            for data in data_list:
                embed.add_field(name=data[0], value=f"Кол-во сообщений: {data[1]}", inline=False)

        await ctx.followup.send(embed=embed, ephemeral=True)

    @commands.slash_command(
    name="delete_listener",
    description="Удалить информацию о пользователях и закончить их счёт"
    )
    async def delete_listener(self, ctx: discord.ApplicationContext):
        if self.listener_params['started'] == "False":
            await ctx.respond("Вы не начали слушание канала")
            return
        
        await ctx.defer()

        if os.path.exists(logs_path):
            shutil.rmtree(str(logs_path))
            os.mkdir(logs_path)
        if os.path.exists(member_data_path):
            os.remove(member_data_path)
        if os.path.exists(logger_params_path):
            with open(logger_params_path, "w+") as params:
                params.write(json.dumps(self.default_listener_params))
                self.listener_params = self.default_listener_params

        await ctx.followup.send("Слушание канала и информация о пользователях удалена!", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if self.listener_params['started'] == "False":
            return
        
        channel = discord.utils.get(message.guild.channels, id=self.listener_params["channel_id"])
        role = discord.utils.get(message.guild.roles, id=self.listener_params['role_id'])
        for member in role.members:
            if message.author.id != member.id or message.channel.id != channel.id:
                continue
            
            message_logs_path = self.create_message_logs_path(message)

            self.write_logs(message_logs_path, str(message.created_at), member.name)

            with open(member_data_path, "r") as data_file:
                self.internal_data = json.loads(data_file.read())
            for member_data in self.internal_data:
                if member_data[0] != message.author.display_name:
                    continue
                
                s = int(member_data[1])
                s += 1
                member_data[1] = str(s)
            with open(member_data_path, "w+") as data_file:
                data_file.write(json.dumps(self.internal_data))
    

    def write_logs(self, logs_path: str, member_name: str, message_create_time: str):
        internal_logs = [[]]
        if os.path.exists(logs_path):
            with open(logs_path, "r") as logs:
                temp: list[list] = json.loads(logs.read())
                internal_logs = temp
        else:
            with open(logs_path, "w"):
                log = [member_name, message_create_time]

        log = [member_name, message_create_time]
        internal_logs.append(log)
        with open(logs_path, "w+") as logs:
            logs.write(json.dumps(internal_logs))


    def create_message_logs_path(self, message: discord.Message) -> str:
        month_year_log_str = f"{message.created_at.date().year}_{message.created_at.date().month}"
        monthly_logs_path = os.path.join(logs_path, f"logs_{month_year_log_str}")

        if not os.path.exists(monthly_logs_path):
            os.mkdir(monthly_logs_path)

        message_logs_path = os.path.join(monthly_logs_path, f"message_logs_{message.created_at.date()}.json")
        return message_logs_path