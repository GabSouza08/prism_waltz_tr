import random
# --- Combat Round ---
# Global battle history list
DEBUG_MODE = False  # Toggle this to False for normal play
battle_history = []
def validate_echo_titles(champions, echo_lookup):

    for champ in champions:
        name = champ.get("name", "Unknown")
        echo_titles = champ.get("echo_titles", [])
        if not echo_titles:
            print(f"⚠️ {name} has no EchoTitles assigned.\n")
            continue

        print(f"👤 Champion: {name}")
        for title in echo_titles:
            echo = echo_lookup.get(title)
            if not echo:
                print(f"  ❌ Missing Echo: '{title}'")
                continue

            # Show Echo details
            effect = echo.effect_type
            target_type = echo.target_type
            ep_cost = echo.ep_cost

            # Flag suspicious target types
            if target_type not in {"self", "ally", "enemy", "aoe_ally", "aoe_enemy"}:
                print(f"  ⚠️ Echo '{title}' has unknown target type: '{target_type}'")
            else:
                print(f"  ✅ '{title}' → Target: {target_type}, EP: {ep_cost}, Effects: {effect}")
        print("")  # Spacer between champions


def infer_target_type(echo_dict):
    return echo_dict.get("target_type", "enemy")  # fallback if missing

class StatusManager:
    def __init__(self):
        self.effects = []

    def add(self, effect_type, duration, value=None, source=None):
        self.effects.append({
            "type": effect_type,
            "duration": duration,
            "value": value,
            "source": source
        })
        print(f"🧬 Added status '{effect_type}' for {duration} turns from '{source}'.")

    def process(self, character):
        for effect in self.effects[:]:  # Clone list to prevent modification during loop
            etype = effect["type"]
            src = effect["source"]
            val = effect.get("value")

            # ✅ Regen heals HP
            if etype == "regen":
                heal = val or 10
                old_hp = character.hp
                character.hp = min(character.max_hp, character.hp + heal)
                actual_heal = character.hp - old_hp
                print(f"🧃 {character.name} regenerates {actual_heal} HP from '{src}'.")

            # ✅ Damage over time
            elif etype == "dot":
                dmg = val or 5
                character.hp = max(character.hp - dmg, 0)
                print(f"🧪 {character.name} takes {dmg} DOT from '{src}'.")

            # ✅ Debuff: stun — flag to skip action
            elif etype == "stun":
                character.skip_turn = True
                print(f"⚡ {character.name} is stunned and cannot act this turn.")

            # ✅ Debuff: freeze
            elif etype == "freeze":
                character.skip_turn = True
                print(f"❄️ {character.name} is frozen and skips this turn.")

            # ✅ Buff: reflect (tracked in damage logic)
            elif etype == "reflect":
                print(f"🪞 {character.name} is ready to reflect damage via '{src}'.")

            # ✅ Buff: dodge (chance-based logic handled elsewhere)
            elif etype == "dodge":
                print(f"🩰 {character.name} may dodge attacks this turn (chance: {int(val * 100)}%).")

            # ✅ Buff: status immunity
            elif etype == "status_immunity":
                print(f"🧭 {character.name} is immune to new status effects.")

            effect["duration"] -= 1
            if effect["duration"] <= 0:
                print(f"⏳ '{etype}' from '{src}' expired for {character.name}.")
                self.effects.remove(effect)

    def has(self, effect_type):
        return any(e["type"] == effect_type for e in self.effects)

    def get(self, effect_type):
        return [e for e in self.effects if e["type"] == effect_type]

    def remove(self, effect_type):
        self.effects = [e for e in self.effects if e["type"] != effect_type]
        print(f"🧹 Removed '{effect_type}' from status effects.")

    def remove_all_buffs(self):
        BUFF_TYPES = {
            "regen", "cloak", "status_immunity", "dodge", "reflect",
            "damage_negation", "ally_protection"
        }
        removed = [e["type"] for e in self.effects if e["type"] in BUFF_TYPES]
        self.effects = [e for e in self.effects if e["type"] not in BUFF_TYPES]
        return removed

    def remove_all_debuffs(self):
        DEBUFF_TYPES = {
            "dot", "stun", "freeze", "silence", "debuff", "slow"
        }
        removed = [e["type"] for e in self.effects if e["type"] in DEBUFF_TYPES]
        self.effects = [e for e in self.effects if e["type"] not in DEBUFF_TYPES]
        return removed

def log(msg):
    print(msg)
    battle_history.append(msg)
        
class Champion:
    def __init__(self, data):
        self.name         = data["name"]
        self.grand_title  = data["grand_title"]
        self.house        = data.get("house")

        # ── Stats ─────────────────────────────────────
        stats      = data["stats"]
        self.max_hp = stats["HP"] + 50
        self.hp     = self.max_hp
        self.atk    = stats["ATK"]
        self.defense= stats["DEF"]
        self.spd    = stats["SPD"]
        # ── Echoes ────────────────────────────────────
        self.echoes = [
            ECHO_LIB[title] for title in data["echo_titles"]
            if title in ECHO_LIB
        ]
        self.ep    = 0
        self.crit_chance     = data.get("crit_chance", 0.10)
        self.crit_multiplier = data.get("crit_multiplier", 2.0)
        self.status_effects = {}  # e.g., {"burn": {"duration": 3, "damage": 5}}
        self.status = StatusManager()
        self.apply_echo_stats()  # ✅ Apply echo bonuses during init
    
    def apply_echo_stats(self):
        bonuses = HOUSE_ECHO_BONUSES.get(self.house)
        if bonuses:
            self.atk += bonuses.get("ATK", 0)
            self.defense += bonuses.get("DEF", 0)
            self.spd += bonuses.get("SPD", 0)
            self.ep += bonuses.get("EP", 0)
            self.hp += bonuses.get("HP", 0)
            self.hp_regen = bonuses.get("HP_REGEN", 0)
            self.echo_description = bonuses.get("description", "")
            self.crit_dodge = bonuses.get("CRIT_DODGE", False)
            self.ep_on_hit = bonuses.get("EP_ON_HIT", 0)
            self.ep_per_turn = bonuses.get("EP_PER_TURN", 0) + 25
            self.atk_if_low_hp = bonuses.get("ATK_IF_LOW_HP", 0)
            self.ep_on_ko_received = bonuses.get("EP_ON_KO_RECEIVED", 0)
            self.immune_turn_delay = bonuses.get("IMMUNE_TURN_DELAY", False)
            self.random_buff = bonuses.get("RANDOM_BUFF", False)

    def show_status(self):
    # Banner line with name, title, and house
      banner = f"🌟 {self.name} [{self.grand_title}] — {self.house}"
      stats = f"HP:{self.hp}/{self.max_hp} | EP:{self.ep} | ATK:{self.atk} | DEF:{self.defense} | SPD:{self.spd}"
      trait = f"Trait ➤ {self.echo_description}" if hasattr(self, "echo_description") else ""
    # Print everything neatly
      print(banner)
      print(f"   {stats}")
      if trait:
        print(f"   {trait}")
        print("-" * 50)

    def is_low_hp(self):
        return self.hp < (self.max_hp * 0.3)
    def is_alive(self):
        return self.hp > 0
    def check_conditional_bonuses(self):
        if self.is_low_hp() and self.atk_if_low_hp and not getattr(self, "low_hp_bonus_applied", False):
            self.atk += self.atk_if_low_hp
            self.low_hp_bonus_applied = True
            print(f"🔥 {self.name} enters critical mode: ATK boosted by {self.atk_if_low_hp}!")


    def basic_attack(self, target):
      is_crit = random.random() < getattr(self, "crit_chance", 0.1)
      crit_multiplier = getattr(self, "crit_multiplier", 1.5) if is_crit else 1.0
      base_damage = max(self.atk - target.defense + random.randint(-5, 5), 5)
      damage = int(base_damage * crit_multiplier)
    # 🧠 Trait synergy: bonus ATK if low HP
      if self.hp < self.max_hp * 0.3:
        damage += getattr(self, "atk_if_low_hp", 0)
    # 🛡️ Target trait: dodge crits
      if is_crit and getattr(target, "crit_dodge", False):
        damage = base_damage  # negate crit bonus
    # 💥 Apply damage
      target.hp -= damage
      if is_crit and getattr(target, "crit_dodge", False):
        damage = base_damage
        battle_history.append(f"{target.name} dodged the critical hit!")
      # 🛡️ Check for shield
      shields = target.status.get("shield")
      if shields:
        shield = shields[0]
        absorbed = min(damage, shield["value"])
        shield["value"] -= absorbed
        damage -= absorbed
        print(f"🛡️ {target.name}'s shield absorbs {absorbed} damage.")
        battle_history.append(f"{target.name}'s shield absorbs {absorbed} damage.")
        if shield["value"] <= 0:
          target.status.remove("shield")
          print(f"💥 {target.name}'s shield is broken!")
          battle_history.append(f"{target.name}'s shield is broken!")


      if target.hp < 0:
          target.hp = 0
    # ⚡ EP gain on hit
      self.ep += getattr(self, "ep_on_hit", 0)
    # ⚰️ EP gain if target is KO'd
      if target.hp == 0:
        self.ep += getattr(self, "ep_on_ko_received", 0)

    # 📜 Build log entry
      log = f"{self.name} attacked {target.name} for {damage} damage."
      if is_crit:
        log += " (CRITICAL HIT!)"
      if target.hp == 0:
        log += f" {target.name} is KO'd!"

    # 🖨️ Print and record
      print(log)
      battle_history.append(log)
      return damage


# =========================
# 🔷 EchoTitle Class
# =========================


class EchoTitle:
    def __init__(self, title, effect_type, stat_modifiers, ep_cost, target_type=None):
        effect_type = effect_type if isinstance(effect_type, list) else [effect_type]
        self.title = title
        self.effect_type = effect_type
        self.stat_modifiers = stat_modifiers or {}
        self.ep_cost = ep_cost
        self.target_type = target_type or infer_target_type(self.effect_type)

    def use(self, user, target=None, allies=None, enemies=None):
        # 🔋 EP Check
        if user.ep < self.ep_cost:
            print(f"⚠️ {user.name} does not have enough EP to cast '{self.title}' ({user.ep}/{self.ep_cost})")
            return

        # ✅ Target Validation
        if not validate_echo_targets(self, user, target, allies or [], enemies or []):
            print(f"❌ {self.title} failed to find a valid target.")
            return

        target_name = target.name if target else "the battlefield"
        battle_history.append(f"{user.name} cast '{self.title}' on {target_name}.")

        # 🔻 Deduct EP
        user.ep -= self.ep_cost

        # 🎯 Apply Effect
        if self.target_type == "enemy":
            if target and target.is_alive():
                self._apply_effect(user, target)
            else:
                print(f"⚠️ Target is invalid or dead for '{self.title}'.")

        elif self.target_type == "ally":
            if target and (target.is_alive() or "revive" in self.effect_type):
                self._apply_effect(user, target)
            else:
                print(f"⚠️ Ally target is invalid or dead for '{self.title}'.")

        elif self.target_type == "self":
            self._apply_effect(user, user)

        elif self.target_type == "aoe_ally":
            for ally in allies or []:
                if ally.is_alive() or "revive" in self.effect_type:
                    self._apply_effect(user, ally)

        elif self.target_type == "aoe_enemy":
            for enemy in enemies or []:
                if enemy.is_alive():
                    self._apply_effect(user, enemy)
        else:
            print(f"⚠️ Unknown target type '{self.target_type}' for Echo '{self.title}'")

    def _apply_effect(self, user, target):
      if not target.is_alive() and "revive" not in self.effect_type:
        log(f"⚠️ Cannot apply '{self.title}' to {target.name} — target is not alive.")
        return

      if "revive" in self.effect_type and not target.is_alive():
        revive_hp = self.stat_modifiers.get("HP", 25)
        target.hp = revive_hp
        log(f"✨ {user.name} revives {target.name} with {revive_hp} HP using '{self.title}'!")
        return

      total_damage = 0

      if "heal" in self.effect_type:
          heal_amount = self.stat_modifiers.get("HP", 0)
          old_hp = target.hp
          target.hp = min(target.max_hp, target.hp + heal_amount)
          actual_heal = target.hp - old_hp
          log(f"💚 {user.name} heals {target.name} for {actual_heal} HP with '{self.title}'.")

      if "bonus_damage" in self.effect_type:
        bonus_atk = self.stat_modifiers.get("ATK", 0)
        missing_hp_bonus = int((user.max_hp - user.hp) / 3)
        raw_damage = (user.atk + bonus_atk + missing_hp_bonus) - target.defense
        damage = max(raw_damage, 1)
        target.hp = max(target.hp - damage, 0)
        total_damage += damage
        log(f"💥 {user.name} deals {damage} bonus damage to {target.name} with '{self.title}'.")

      if "burn" in self.effect_type or "burn" in self.effect_type:
          log(f"🔥 {target.name} is afflicted with burn from '{self.title}'.")

      if "def_buff" in self.effect_type:
        def_increase = self.stat_modifiers.get("DEF", 0)
        old_def = target.defense
        target.defense += def_increase
        log(f"🛡️ {target.name}'s DEF increased by {def_increase} (from {old_def} to {target.defense}) via '{self.title}'.")

      if "atk_buff" in self.effect_type:
        atk_increase = self.stat_modifiers.get("ATK", 0)
        old_atk = target.atk
        target.atk += atk_increase
        log(f"⚔️ {target.name}'s ATK increased by {atk_increase} (from {old_atk} to {target.atk}) via '{self.title}'.")

      if "spd_buff" in self.effect_type:
        spd_increase = self.stat_modifiers.get("SPD", 0)
        old_spd = target.spd
        target.spd += spd_increase
        log(f"💨 {target.name}'s SPD increased by {spd_increase} (from {old_spd} to {target.spd}) via '{self.title}'.")

      if "ep_gain" in self.effect_type:
        ep_boost = self.stat_modifiers.get("EP", 0)
        user.ep = min(user.ep + ep_boost, 100)
        log(f"🔋 {user.name} gains {ep_boost} EP from '{self.title}'.")

      if "lifesteal" in self.effect_type and total_damage > 0:
        heal = int(total_damage * 0.3)
        user.hp = min(user.max_hp, user.hp + heal)
        log(f"🩸 {user.name} steals {heal} HP from {target.name} via '{self.title}'.")

      if "regen" in self.effect_type:
        target.status.add("regen", duration=3, value=self.stat_modifiers.get("HP", 10), source=self.title)
        log(f"🧃 {target.name} gains regeneration for 3 turns via '{self.title}'.")

      if "status_immunity" in self.effect_type:
        target.status.add("status_immunity", duration=2, source=self.title)
        log(f"🧭 {target.name} is immune to status effects for 2 turns via '{self.title}'.")

      if "buff_removal" in self.effect_type:
        removed = target.status.remove_all_buffs()
        log(f"🧹 {target.name}'s buffs removed by '{self.title}' → {removed or 'none'}.")

      if "debuff_removal" in self.effect_type:
        removed = target.status.remove_all_debuffs()
        log(f"🧼 {target.name}'s debuffs cleansed by '{self.title}' → {removed or 'none'}.")

      if "stun" in self.effect_type:
        target.status.add("stun", duration=1, source=self.title)
        log(f"⚡ {target.name} is stunned by '{self.title}' and loses their next turn.")

      if "freeze" in self.effect_type:
        target.status.add("freeze", duration=1, source=self.title)
        log(f"❄️ {target.name} is frozen by '{self.title}' and cannot act next turn.")

      if "silence" in self.effect_type:
        target.status.add("silence", duration=2, source=self.title)
        log(f"🔇 {target.name} is silenced by '{self.title}' and cannot cast Echoes.")

      if "slow" in self.effect_type:
        slow_amount = self.stat_modifiers.get("SPD", 0)
        target.spd = max(target.spd - slow_amount, 1)
        log(f"🐢 {target.name}'s SPD is reduced by {slow_amount} via '{self.title}'.")

      if "debuff" in self.effect_type:
        target.status.add("debuff", duration=2, source=self.title)
        log(f"🌀 {target.name} is afflicted with a debuff via '{self.title}'.")

      if "dot" in self.effect_type:
        dot_value = self.stat_modifiers.get("ATK", 5)
        target.status.add("dot", duration=3, value=dot_value, source=self.title)
        log(f"🧪 {target.name} suffers {dot_value} DOT for 3 turns via '{self.title}'.")

      if "aoe_damage" in self.effect_type:
        aoe_multiplier = 0.75
        damage = int(user.atk * aoe_multiplier)
        target.hp = max(target.hp - damage, 0)
        log(f"🌋 {user.name} deals {damage} AOE damage to {target.name} with '{self.title}'.")

      if "def_ignore" in self.effect_type:
        target.status.add("def_ignore", duration=1, source=self.title)
        log(f"🧨 {user.name}'s attack ignores DEF via '{self.title}'.")

      if "burst" in self.effect_type:
        burst_damage = int(user.atk * 0.75)
        target.hp -= burst_damage
        log(f"💥 Burst from '{self.title}' deals {burst_damage} bonus damage to {target.name}!")

      if "taunt" in self.effect_type:
        target.status.add("taunt", duration=2, value=user.name, source=self.title)
        log(f"🎯 {target.name} is forced to target {user.name} due to '{self.title}'.")

      if "cloak" in self.effect_type:
        target.status.add("cloak", duration=1, source=self.title)
        log(f"🕶️ {target.name} becomes cloaked via '{self.title}' and cannot be targeted.")

      if "dodge" in self.effect_type:
        chance = self.stat_modifiers.get("DODGE", 0.25)
        target.status.add("dodge", duration=2, value=chance, source=self.title)
        log(f"🩰 {target.name} gains {int(chance * 100)}% dodge chance via '{self.title}'.")

      if "reflect" in self.effect_type:
        target.status.add("reflect", duration=1, source=self.title)
        log(f"🪞 {target.name} gains reflect from '{self.title}'.")

      if "damage_negation" in self.effect_type:
        target.status.add("damage_negation", duration=1, source=self.title)
        log(f"🛡️ {target.name} will negate incoming damage via '{self.title}'.")

      if "ally_protection" in self.effect_type:
        target.status.add("ally_protection", duration=2, value=target.name, source=self.title)
        log(f"🛡️ {target.name} protects their allies via '{self.title}'.")

      if "shield" in self.effect_type:
        shield_value = self.stat_modifiers.get("HP", 30)
        duration = self.stat_modifiers.get("DURATION", 2)
        target.status.add("shield", duration=duration, value=shield_value, source=self.title)
        log(f"🛡️ {target.name} gains a shield of {shield_value} HP for {duration} turns via '{self.title}'.")




# --- Echo Bonuses Dictionary ---
HOUSE_ECHO_BONUSES = {
    "Scarlet": {
        "ATK": 5,
        "DEF": 3,
        "description": "🔥 Sincere and resolute, Scarlet champions strike with unyielding passion."
    },
    "Alizarin": {
        "CRIT": 4,
        "SPD": 3,
        "description": "🎨 Brilliance through expression—Alizarin minds inspire precise, creative bursts."
    },
    "Violet": {
        "EP": 5,
        "HP_REGEN": 2,
        "DEF": -2,
        "description": "🌌 Gentle power born from silence—Violet healers endure quietly and recover steadily."
    },
    "Purpur": {
        "SPD": 3,
        "RANDOM_BUFF": True,
        "description": "🪞 Tricksters by nature—Purpur echoes reveal truth through illusion and mischief."
    },
    "Orelian": {
        "DEF": 3,
        "ATK": 4,
        "description": "🏛️ Builders of order—Orelian champions grow strong through memory and structure."
    },
    "Iridion": {
        "SPD": 2,
        "EP_ON_HIT": 5,
        "description": "🌠 Veilwalkers emerge from ambiguity—Iridion channels mystery into radiant potential."
    },
    "Rosarium": {
        "DEF": 3,
        "HP_REGEN": 2,
        "ATK_IF_LOW_HP": 5,
        "description": "🌸 From sorrow blooms strength—Rosarium echoes rise beautifully when wounded."
    },
    "Olive": {
        "DEF": 2,
        "SPD": 3,
        "CRIT_DODGE": True,
        "description": "🕊️ Guardians of calm—Olive minds flow through peace, dodging chaos without noise."
    },
    "Onyx": {
        "ATK_IF_LOW_HP": 5,
        "EP_ON_KO_RECEIVED": 10,
        "description": "🩸 Resilience carved from ruin—Onyx thrives in the broken aftermath of hardship."
    },
    "Ivory": {
        "EP_PER_TURN": 2,
        "IMMUNE_TURN_DELAY": True,
        "description": "🌤️ Seekers of long-lost clarity—Ivory champions scale slowly toward luminous truth."
    }
}

houses = {
    "Scarlet": [
        {
            "name": "Eduardo Carlos",
            "grand_title": "Golden Aegis Keeper",
            "echo_titles": ["Pyreborn Testament", "Ember's Final Whisper"],
            "stats": {"HP": 145, "ATK": 30, "DEF": 48, "SPD": 28}
        },
        {
            "name": "Ana Clara",
            "grand_title": "Daughter of Serenity's Verse",
            "echo_titles": ["Tethered Echostep", "Bloom of Shared Wanderings"],
            "stats": {"HP": 125, "ATK": 35, "DEF": 30, "SPD": 40}
        },
        {
            "name": "Carlos Antonio",
            "grand_title": "Guardian of Quiet Flame",
            "echo_titles": ["Vestige of Silent Rage", "Vigil of Broken Honor"],
            "stats": {"HP": 150, "ATK": 32, "DEF": 50, "SPD": 25}
        },
        {
            "name": "Sara Regina",
            "grand_title": "Resolute Flamebearer",
            "echo_titles": ["Plaguebearer of Fevered Ambitions", "Bane of Trembling Courage"],
            "stats": {"HP": 135, "ATK": 45, "DEF": 35, "SPD": 30}
        },
        {
            "name": "João Vitor",
            "grand_title": "Bulwark of the Ember Crown",
            "echo_titles": ["Rampart of Welcomed Oblivion", "Bulwark of Chosen Torment"],
            "stats": {"HP": 150, "ATK": 28, "DEF": 50, "SPD": 27}
        },
        {
            "name": "Sabrina Silva",
            "grand_title": "Crown of Blazing Resolve",
            "echo_titles": ["Guide of Beyond Regret", "Waltz of Rediscovered Rhythms"],
            "stats": {"HP": 130, "ATK": 38, "DEF": 40, "SPD": 35}
        },
        {
            "name": "Davi Luiz",
            "grand_title": "Sunlit Rampart Protector",
            "echo_titles": ["Forge of Unyielding Belief", "Sentinel of Bending Truths"],
            "stats": {"HP": 140, "ATK": 32, "DEF": 48, "SPD": 30}
        },
        {
            "name": "Maria Clara",
            "grand_title": "Dawnlit Emissary",
            "echo_titles": ["Murmur of Broken Hopes", "Legend of Silent Sorrow"],
            "stats": {"HP": 120, "ATK": 42, "DEF": 28, "SPD": 45}
        },
        {
            "name": "Jefferson Lucas",
            "grand_title": "Vanguard of the Sunwave",
            "echo_titles": ["Chorus of Broken Hope", "Lament of Fading Trust"],
            "stats": {"HP": 145, "ATK": 44, "DEF": 40, "SPD": 32}
        },
        {
            "name": "Maria Cecília",
            "grand_title": "Rose of the Ember Chapel",
            "echo_titles": ["Burdenbearer's Final Stand", "Bloodwritten Oath"],
            "stats": {"HP": 125, "ATK": 36, "DEF": 35, "SPD": 38}
        },
        {
            "name": "Matthews Guedes",
            "grand_title": "Rampart-Warden of Dawn",
            "echo_titles": ["Pupil of Crimson Betrayal", "Trailblazer of Unholy Power"],
            "stats": {"HP": 150, "ATK": 30, "DEF": 50, "SPD": 28}
        },
        {
            "name": "Maria Luisa",
            "grand_title": "Brightvoice Oracle",
            "echo_titles": ["Chorus of Mended Bonds", "Verse of Parting Joy"],
            "stats": {"HP": 120, "ATK": 38, "DEF": 30, "SPD": 42}
        },
        {
            "name": "Heleno Gomes",
            "grand_title": "Bastion-Watcher of Daybreak",
            "echo_titles": ["Emptiness's Herald", "Harbinger of Hollow Resolve"],
            "stats": {"HP": 150, "ATK": 32, "DEF": 50, "SPD": 25}
        },
        {
            "name": "Elen Nayara",
            "grand_title": "Lantern of Morning Mist",
            "echo_titles": ["Surface Whispers of Passage", "Tide of Unheard Ballads"],
            "stats": {"HP": 115, "ATK": 40, "DEF": 30, "SPD": 48}
        },
        {
            "name": "Rodrigo Bezerra",
            "grand_title": "Ironflare Duelist",
            "echo_titles": ["Silencebreak's Critic", "Laughter's Final Bane"],
            "stats": {"HP": 110, "ATK": 50, "DEF": 28, "SPD": 50}
        },
        {
            "name": "Esthella Angelina",
            "grand_title": "Nightlight's Counterpoint",
            "echo_titles": ["Baptizer of Burning Anger", "Flame of Unquenchable Hate"],
            "stats": {"HP": 130, "ATK": 48, "DEF": 30, "SPD": 45}
        }
    ],
"Violet": [
        {
            "name": "Carlos Eduardo",
            "grand_title": "Warden of the Twilight Gate",
            "echo_titles": ["Dreamwright's Rebirth", "Beacon of New Ruins"],
            "stats": {"HP": 145, "ATK": 30, "DEF": 48, "SPD": 27}
        },
        {
            "name": "Evellyn Oliveira",
            "grand_title": "Photon-Shield Maiden",
            "echo_titles": ["Shield of Shattered Promises", "Maiden of Regret's Dawn"],
            "stats": {"HP": 130, "ATK": 35, "DEF": 40, "SPD": 35}
        },
        {
            "name": "José Izaquiel",
            "grand_title": "Oracle of Moon Blessings",
            "echo_titles": ["Breath of Bound Fate", "Cipher of Unbroken Threads"],
            "stats": {"HP": 120, "ATK": 45, "DEF": 30, "SPD": 45}
        },
        {
            "name": "Bianca Flora",
            "grand_title": "Petalwing Sentinel",
            "echo_titles": ["Petal of Fraying Hope", "Whisper of Fading Tethers"],
            "stats": {"HP": 125, "ATK": 40, "DEF": 35, "SPD": 40}
        },
        {
            "name": "Josenilton Oliveira",
            "grand_title": "Bronze-Crescent Keeper",
            "echo_titles": ["Defender of Born Legacies", "Pathcarver of Fleeting Honors"],
            "stats": {"HP": 150, "ATK": 28, "DEF": 50, "SPD": 26}
        },
        {
            "name": "Maria Yasmim",
            "grand_title": "Bloomheart Whisperer",
            "echo_titles": ["Quill of Untold Saga", "Blade of Renewed Ruin"],
            "stats": {"HP": 130, "ATK": 38, "DEF": 36, "SPD": 42}
        },
        {
            "name": "João Pedro",
            "grand_title": "Celestial Pathway Herald",
            "echo_titles": ["Rhythm of Missed Steps", "Echo of Unwalked Paths"],
            "stats": {"HP": 115, "ATK": 42, "DEF": 28, "SPD": 48}
        },
        {
            "name": "Ana Victoria",
            "grand_title": "Moon-Fused Resolve",
            "echo_titles": ["Death's Curiosity Catalyst", "Slayer of Unasked Questions"],
            "stats": {"HP": 110, "ATK": 50, "DEF": 27, "SPD": 50}
        },
        {
            "name": "Manoel Henrique",
            "grand_title": "Echo of the Nightshield",
            "echo_titles": ["Bond of Returned Burdens", "Knuckles of Vengeful Pardon"],
            "stats": {"HP": 145, "ATK": 32, "DEF": 48, "SPD": 30}
        },
        {
            "name": "Emilly Alves",
            "grand_title": "Pulse of Velvet Reflection",
            "echo_titles": ["Echo of Applause Lost", "Reflection of Hollow Cheers"],
            "stats": {"HP": 125, "ATK": 36, "DEF": 34, "SPD": 45}
        },
        {
            "name": "Jobson Santana",
            "grand_title": "Moonlit Wanderer",
            "echo_titles": ["Step of the Untraced Night", "Chord of Forgotten Starlight"],
            "stats": {"HP": 135,"ATK": 44,"DEF": 33,"SPD": 38}
        },
        {
            "name": "Samantha Martinez",
            "grand_title": "Waltz of Velvet Resolve",
            "echo_titles": ["Mirrorcrack Echo", "Splinter of True Reflection"],
            "stats": {"HP": 120, "ATK": 40, "DEF": 30, "SPD": 50}
        },
        {
            "name": "Jonathan Nazareno",
            "grand_title": "Seeker of Silver Fates",
            "echo_titles": ["Whisper of Shattered Glory", "Remnant of Fallen Triumph"],
            "stats": {"HP": 135, "ATK": 44, "DEF": 33, "SPD": 38}
        },
        {
            "name": "Mirelle Freitas",
            "grand_title": "Dreamtide Luminary",
            "echo_titles": ["Dancer of War's Lullaby", "Weaver of Nightmare Steps"],
            "stats": {"HP": 115, "ATK": 48, "DEF": 29, "SPD": 45}
        },
        {
            "name": "Ricardo Henrique",
            "grand_title": "Starlight Herald",
            "echo_titles": ["Carver of Vengeance Scars", "Scrawl of Unyielding Wrath"],
            "stats": {"HP": 130, "ATK": 42, "DEF": 36, "SPD": 40}
        },
        {
            "name": "Vitoria Karoline",
            "grand_title": "Champion of Moonlit Wills",
            "echo_titles": ["Smile of Regretted Echo", "Reflection of Loud Regrets"],
            "stats": {"HP": 125, "ATK": 38, "DEF": 35, "SPD": 45}
        }
    ],
"Purpur": [
    {
        "name": "Arthur Ivandro",
        "grand_title": "Bearer of the Moonrise Fury",
        "echo_titles": ["Ruinforged Monument", "Corpse-stitched Aspiration"],
        "stats": {"HP": 115, "ATK": 48, "DEF": 30, "SPD": 45}
    },
    {
        "name": "Ketillyn Irlly",
        "grand_title": "Silver-Dusk Trickster",
        "echo_titles": ["Wraith of Stolen Vengeance", "Shadow of Reclaimed Will"],
        "stats": {"HP": 105, "ATK": 45, "DEF": 28, "SPD": 50}
    },
    {
        "name": "David Erick",
        "grand_title": "Shadow-Wall Duelist",
        "echo_titles": ["Edge of Curious Revelation", "Blade of Uncertain Truths"],
        "stats": {"HP": 120, "ATK": 42, "DEF": 35, "SPD": 40}
    },
    {
        "name": "Bruna Evelyn",
        "grand_title": "Silken Moonblade",
        "echo_titles": ["Weave of Enduring Fears", "Ballad of True Pain"],
        "stats": {"HP": 110, "ATK": 44, "DEF": 30, "SPD": 48}
    },
    {
        "name": "Gabriel Andre",
        "grand_title": "Dawnbreaker of Dusk",
        "echo_titles": ["Antidote of Unshaken Will", "Cure of Quivering Fears"],
        "stats": {"HP": 140, "ATK": 30, "DEF": 48, "SPD": 28}
    },
    {
        "name": "Mariana Pontes",
        "grand_title": "Mistbringer of Tidecall",
        "echo_titles": ["Sculptor of Rising Ashes", "Tide of Messy Genesis"],
        "stats": {"HP": 130, "ATK": 38, "DEF": 38, "SPD": 30}
    },
    {
        "name": "Gabriel Lucena",
        "grand_title": "Nocturnal Cipher Avenger",
        "echo_titles": ["Virus of Perfect Lies", "Script of Twisted Reflections"],
        "stats": {"HP": 105, "ATK": 50, "DEF": 25, "SPD": 50}
    },
    {
        "name": "Isadora Andrade",
        "grand_title": "Mirrorblade of Lunar Valor",
        "echo_titles": ["Muse of Forgotten Alms", "Shadow of Vanished Love"],
        "stats": {"HP": 115, "ATK": 45, "DEF": 30, "SPD": 42}
    },
    {
        "name": "Henrique Floripe",
        "grand_title": "Moonlit Sovereign",
        "echo_titles": ["Blade of Faith Unmade", "Warden of Fallen Vanity"],
        "stats": {"HP": 150, "ATK": 32, "DEF": 50, "SPD": 26}
    },
    {
        "name": "Karoline Cassiano",
        "grand_title": "Moonflare Visionary",
        "echo_titles": ["Narrator of Reborn Tales", "Scarlet of Ruin's Renewal"],
        "stats": {"HP": 135, "ATK": 40, "DEF": 40, "SPD": 35}
    },
    {
        "name": "Leonardo Lyon",
        "grand_title": "Howl of the Lunar Citadel",
        "echo_titles": ["Threadsnare Unraveled", "Weaver of Final Severance"],
        "stats": {"HP": 145, "ATK": 35, "DEF": 45, "SPD": 30}
    },
    {
        "name": "Emilly Nayara",
        "grand_title": "Nightbloom Chanter",
        "echo_titles": ["Motionbound Liberation", "Petals of Parting Unity"],
        "stats": {"HP": 120, "ATK": 38, "DEF": 35, "SPD": 40}
    },
    {
        "name": "Ronald Bryan",
        "grand_title": "Twilight Harbinger",
        "echo_titles": ["Penitent's Unspoken Cries", "Blade of Forgiven Silence"],
        "stats": {"HP": 125, "ATK": 48, "DEF": 30, "SPD": 45}
    },
    {
        "name": "Fabielly Fonseca",
        "grand_title": "Silken Nightsong",
        "echo_titles": ["Mercy's Last Echo", "Shard of Fractured Devotion"],
        "stats": {"HP": 130, "ATK": 36, "DEF": 36, "SPD": 42}
    },
    {
        "name": "Thales Santana",
        "grand_title": "Tidecall Duelist of Night",
        "echo_titles": ["Keeper of Fragile Lucidity", "Tether of Last Grip"],
        "stats": {"HP": 115, "ATK": 46, "DEF": 28, "SPD": 48}
    },
    {
        "name": "Sophia Romero",
        "grand_title": "Midnight Song Sovereign",
        "echo_titles": ["Echo of Sistered Laughter", "Fray of Farewell Mirth"],
        "stats": {"HP": 125, "ATK": 40, "DEF": 35, "SPD": 45}
    }
    ],
"Alizarin": [
    {
        "name": "Achiles Martins",
        "grand_title": "The Radiant Spear",
        "echo_titles": ["Echo of Lost Resolve", "Dirge of the Forgotten Oath"],
        "stats": {"HP": 120, "ATK": 48, "DEF": 30, "SPD": 45}
    },
    {
        "name": "Andrielly Luiz",
        "grand_title": "Echo of Solar Whispers",
        "echo_titles": ["Elegy of Tearborn Steel", "Creation's Last Lament"],
        "stats": {"HP": 110, "ATK": 50, "DEF": 25, "SPD": 50}
    },
    {
        "name": "Adriel Melo",
        "grand_title": "Herald of the Golden Dawn",
        "echo_titles": ["Rhyme of Unbent Conviction", "Echo of Shattered Shields"],
        "stats": {"HP": 150, "ATK": 30, "DEF": 50, "SPD": 25}
    },
    {
        "name": "Bruna Adrielly",
        "grand_title": "Ashen Dawn Crusader",
        "echo_titles": ["Artisan of Final Creation", "Conflagration's Masterpiece"],
        "stats": {"HP": 130, "ATK": 40, "DEF": 40, "SPD": 30}
    },
    {
        "name": "Anderson Marinho",
        "grand_title": "Hearthstone Sentinel",
        "echo_titles": ["Regretforged Pathwalker", "Echoes of Carved Lessons"],
        "stats": {"HP": 145, "ATK": 28, "DEF": 48, "SPD": 27}
    },
    {
        "name": "Damylle Kemilly",
        "grand_title": "Ember-Tide Chantress",
        "echo_titles": ["Roar of Unsilenced Sorrow", "Requiem of the Broken Blade"],
        "stats": {"HP": 125, "ATK": 45, "DEF": 35, "SPD": 40}
    },
    {
        "name": "Arthur Lucas",
        "grand_title": "Crestbearer of Sunstone Rhyme",
        "echo_titles": ["Architect of War Dreams", "Builder of Battlefield Echoes"],
        "stats": {"HP": 135, "ATK": 42, "DEF": 38, "SPD": 35}
    },
    {
        "name": "Rayelle Marinho",
        "grand_title": "Ember-Faced Virtuoso",
        "echo_titles": ["Veil of Vanishing Hopes", "Flame of Last Respite"],
        "stats": {"HP": 105, "ATK": 49, "DEF": 28, "SPD": 50}
    },
    {
        "name": "Brian Morone",
        "grand_title": "Charcoal Beacon",
        "echo_titles": ["Testimony of Blooded Teachings", "Accusation in Crescendo"],
        "stats": {"HP": 150, "ATK": 28, "DEF": 50, "SPD": 25}
    },
    {
        "name": "Marilia Oliveira",
        "grand_title": "Scarlet-Pulse Emissary",
        "echo_titles": ["Song of Enduring Reality", "Beacon of Unyielding Beauty"],
        "stats": {"HP": 130, "ATK": 35, "DEF": 45, "SPD": 30}
    },
    {
        "name": "Felipe Emmanuel",
        "grand_title": "Lightbearer of the First Ray",
        "echo_titles": ["Vanguard of Coveted Legacies", "Ray of Unbowed Heritage"],
        "stats": {"HP": 115, "ATK": 50, "DEF": 30, "SPD": 45}
    },
    {
        "name": "Evellyn Kauany",
        "grand_title": "Photon-Shield Maiden",
        "echo_titles": ["Shadow's Faith Wielder", "Vanity's Final Embrace"],
        "stats": {"HP": 145, "ATK": 30, "DEF": 50, "SPD": 28}
    },
    {
        "name": "Gabriel Lacerda",
        "grand_title": "Seeker of Solar Chants",
        "echo_titles": ["Patch of Restored Truth", "Echofixer of Fractured Voices"],
        "stats": {"HP": 125, "ATK": 38, "DEF": 38, "SPD": 40}
    },
    {
        "name": "Wellen Adelaide",
        "grand_title": "Waveborn Flame",
        "echo_titles": ["Current of Silent Stories", "Melody of Hidden Longings"],
        "stats": {"HP": 135, "ATK": 40, "DEF": 35, "SPD": 45}
    },
    {
        "name": "Tulyo Martins",
        "grand_title": "Morningstar Bard",
        "echo_titles": ["Bard of Approaching End", "Guide to Crimson Exits"],
        "stats": {"HP": 110, "ATK": 48, "DEF": 28, "SPD": 50}
    },
    {
        "name": "Maria Jullya",
        "grand_title": "Solar-Star Oracle",
        "echo_titles": ["Shatterbound Silhouette", "Fragment of Self-Sight"],
        "stats": {"HP": 120, "ATK": 35, "DEF": 40, "SPD": 42}
    }
    ],
"Onyx": [
    {
        "name": "Furina de Fontaine",
        "grand_title": "Sovereign of Dual Verdicts",
        "echo_titles": ["Aria of Tidal Judgment", "Saltborn Veilbreaker"],
        "stats": {"HP": 110, "ATK": 45, "DEF": 30, "SPD": 50}
    },
    {
        "name": "Noelle von Mondstadt",
        "grand_title": "Maiden of the Unbroken Bulwark",
        "echo_titles": ["Hammering Spiral of Grace", "Geode Vow Ascendant"],
        "stats": {"HP": 150, "ATK": 30, "DEF": 50, "SPD": 25}
    },
    {
        "name": "Xiao Alatus",
        "grand_title": "Vigil of the Yaksha Eclipse",
        "echo_titles": ["Winds of Lacerated Karma", "Soulstrike in Hollow Skies"],
        "stats": {"HP": 120, "ATK": 50, "DEF": 25, "SPD": 50}
    },
    {
        "name": "Sakuya Izayoi",
        "grand_title": "Clockmistress of Frozen Seconds",
        "echo_titles": ["Chronoblade Waltz", "Bloom of Stasis Rift"],
        "stats": {"HP": 115, "ATK": 35, "DEF": 40, "SPD": 45}
    },
    {
        "name": "Flandre Scarlet",
        "grand_title": "Crimson Catalyst of Fractal Descent",
        "echo_titles": ["Redshift Spark of Ruin", "Glasswing Chaos Pulse"],
        "stats": {"HP": 125, "ATK": 50, "DEF": 28, "SPD": 48}
    },
    {
        "name": "Son Goku",
        "grand_title": "Transcendent Fist of Boundless Will",
        "echo_titles": ["Limitless Sunflare Drive", "Piercing Spirit Blitz"],
        "stats": {"HP": 150, "ATK": 50, "DEF": 35, "SPD": 50}
    },
    {
        "name": "Makoto Niijima",
        "grand_title": "Justice Phantom of the Iron Heart",
        "echo_titles": ["Atomic Chainbreaker Verdict", "Rogue Bloom Rebellion"],
        "stats": {"HP": 135, "ATK": 40, "DEF": 45, "SPD": 30}
    },
    {
        "name": "Leon Kennedy",
        "grand_title": "Agent of the Viral Eclipse",
        "echo_titles": ["Survivor of Reckoning's Shroud", "Silver Sentinel of the Undead Hour"],
        "stats": {"HP": 140, "ATK": 45, "DEF": 40, "SPD": 30}
    },
    {
        "name": "Aloy Elizabet",
        "grand_title": "Seeker of the Forgotten Spark",
        "echo_titles": ["Flamehair of the Fractured Code", "Echo Huntress of the Shattered Bloom"],
        "stats": {"HP": 130, "ATK": 47, "DEF": 35, "SPD": 40}
    },
    {
        "name": "Geralt of Rivia",
        "grand_title": "White Wolf of the Shrouded Hex",
        "echo_titles": ["Signs of Wolfblood Vow", "Blade of Twilit Reckoning"],
        "stats": {"HP": 145, "ATK": 50, "DEF": 45, "SPD": 35}
    },
    {
        "name": "Arthur Morgan",
        "grand_title": "Oathworn Drifter of Dust and Ash",
        "echo_titles": ["Hollowshot Redemption", "Stampede of the Bitter Creed"],
        "stats": {"HP": 150, "ATK": 48, "DEF": 40, "SPD": 30}
    },
    {
        "name": "Joel Miller",
        "grand_title": "Fractured Sentinel of Found Hope",
        "echo_titles": ["Last Gift Eruption", "Echoes Beneath Spores"],
        "stats": {"HP": 140, "ATK": 42, "DEF": 45, "SPD": 28}
    },
    {
        "name": "Bayonetta Cereza",
        "grand_title": "Umbra Witch of the Velvet Eclipse",
        "echo_titles": ["Bullet Aria of Forgotten Grace", "Witchtime Waltz of Eternal Dusk"],
        "stats": {"HP": 120, "ATK": 50, "DEF": 30, "SPD": 50}
    },
    {
        "name": "Dante Sparda",
        "grand_title": "Devil-Split Vanguard of the Crimson Rift",
        "echo_titles": ["Rebellion Aria", "Riftstorm Crescendo"],
        "stats": {"HP": 150, "ATK": 50, "DEF": 40, "SPD": 45}
    },
    {
        "name": "Vergil Sparda",
        "grand_title": "Dirge Seeker of the Sword Refrain",
        "echo_titles": ["Judgment Cut Nocturne", "Hollow Flash Waltz"],
        "stats": {"HP": 150, "ATK": 50, "DEF": 38, "SPD": 47}
    },
    {
        "name": "Aisha of Andros",
        "grand_title": "Wave Dancer of the Sapphire Bloom",
        "echo_titles": ["Tidesurge Spiral", "Aqua Vortex Waltz"],
        "stats": {"HP": 110, "ATK": 40, "DEF": 32, "SPD": 50}
    }
    ],
"Ivory": [
    {
        "name": "Chapolin Colorado",
        "grand_title": "Crimson Knight of Unlikely Salvation",
        "echo_titles": ["Punch of Noble Folly", "Heroic Echo of the Tiny Titan"],
        "stats": {"HP": 105, "ATK": 45, "DEF": 30, "SPD": 40}
    },
    {
        "name": "Cloud Strife",
        "grand_title": "Soldier of the Broken Sky",
        "echo_titles": ["Buster Blade of Memory's Rift", "Meteorheart of the Fading Stream"],
        "stats": {"HP": 150, "ATK": 50, "DEF": 45, "SPD": 35}
    },
    {
        "name": "Kaeya Alberich",
        "grand_title": "Frostwind Swordsman of Forgotten Blood",
        "echo_titles": ["Velvet Schemer of the Hidden Veil", "Cryo Waltz of the Lost Lineage"],
        "stats": {"HP": 130, "ATK": 40, "DEF": 35, "SPD": 45}
    },
    {
        "name": "Bloom Peters",
        "grand_title": "Flameheart Princess of Enchanted Fire",
        "echo_titles": ["Dragon Spark Halo", "Pyroburst Petalstorm"],
        "stats": {"HP": 115, "ATK": 50, "DEF": 25, "SPD": 45}
    },
    {
        "name": "Kazuma Satou",
        "grand_title": "Luckbound Vagabond of Cosmic Irony",
        "echo_titles": ["Misfortune's Gambitblade", "Echo Trickster of Stolen Triumphs"],
        "stats": {"HP": 120, "ATK": 48, "DEF": 25, "SPD": 50}
    },
    {
        "name": "Violet Evergarden",
        "grand_title": "Ballad Sniper of Memory's Quill",
        "echo_titles": ["Gilded Trigger of Emotion's Resurgence", "Letterblade of Silent Catharsis"],
        "stats": {"HP": 140, "ATK": 30, "DEF": 40, "SPD": 30}
    },
    {
        "name": "Artoria Pendragon",
        "grand_title": "Sacred Regent of the Gleaming Blade",
        "echo_titles": ["Lionheart Echo of Noble Oaths", "Excalibur's Vowborne Radiance"],
        "stats": {"HP": 150, "ATK": 45, "DEF": 50, "SPD": 25}
    },
    {
        "name": "Cirilla Riannon",
        "grand_title": "Timelost Princess of the Shifting Path",
        "echo_titles": ["Elder Blood Surge of the Echo Rift", "Wild Huntbreaker of Ancestral Storms"],
        "stats": {"HP": 135, "ATK": 35, "DEF": 45, "SPD": 40}
    },
    {
        "name": "Yuna Braska",
        "grand_title": "Pilgrim Summoner of the Quiet Dawn",
        "echo_titles": ["Echo Aeon of Soft Sacrifice", "Faithwave of the Lunar Prayer"],
        "stats": {"HP": 125, "ATK": 30, "DEF": 35, "SPD": 50}
    },
    {
        "name": "Lucy Kushinada",
        "grand_title": "Hushed Vanguard of Digital Dreams",
        "echo_titles": ["Neon Petal of Broken Futures", "Echo Phantom of Silent Signalshine"],
        "stats": {"HP": 110, "ATK": 50, "DEF": 25, "SPD": 45}
    },
    {
        "name": "Motoko Kusanagi",
        "grand_title": "Cyber Sentinel of Recursive Thought",
        "echo_titles": ["Ghostthread of Echo Synchrony", "Tactician's Mindforge of Memory Logic"],
        "stats": {"HP": 145, "ATK": 40, "DEF": 50, "SPD": 30}
    },
    {
        "name": "Asuka Soryu",
        "grand_title": "Fiery Valkyrie of Inner Ruin",
        "echo_titles": ["Spiral Lance of Blazing Psyche", "Echoflare of Unyielding Brilliance"],
        "stats": {"HP": 130, "ATK": 50, "DEF": 28, "SPD": 45}
    },
    {
        "name": "Rei Ayanami",
        "grand_title": "Moonborne Seer of Soul Echoes",
        "echo_titles": ["Stellar Requiem of Silent Knowing", "Echo Pulse of the Eternal Child"],
        "stats": {"HP": 105, "ATK": 25, "DEF": 35, "SPD": 30}
    },
    {
        "name": "Adrian Tepes",
        "grand_title": "Nocturne Tactician of Bloodbound Twilight",
        "echo_titles": ["Moonfang Echo of Sorrow's Legacy", "Gothblade of the Eternal Midnight"],
        "stats": {"HP": 150, "ATK": 35, "DEF": 45, "SPD": 28}
    },
    {
        "name": "Howl Pendragon",
        "grand_title": "Whimwoven Arcanist of Stardust Entropy",
        "echo_titles": ["Echo Drift of Heartshaped Chaos", "Featherspell of the Fading Sky"],
        "stats": {"HP": 115, "ATK": 30, "DEF": 40, "SPD": 50}
    },
    {
        "name": "Edward Elric",
        "grand_title": "Crimson Alchemist of Fractured Truth",
        "echo_titles": ["Goldseal Transmutation of Echo Guilt", "Soulbound Mechanist of the Lost Limb"],
        "stats": {"HP": 140, "ATK": 50, "DEF": 35, "SPD": 45}
    }
    ],
"Orelian": [
    {
        "name": "Luna Valentine",
        "grand_title": "Moonlit Enchantress of the Hidden Sonata",
        "echo_titles": ["Silver Lullaby of Waning Dreams", "Echo Embrace of Night's Refrain"],
        "stats": {"HP": 120, "ATK": 35, "DEF": 45, "SPD": 30}
    },
    {
        "name": "Karlotte Smith",
        "grand_title": "Steel-Willed Emissary of the Iron Resolve",
        "echo_titles": ["Echo Bastion of Unbroken Vow", "Crimson Ward of Silent Fortitude"],
        "stats": {"HP": 145, "ATK": 40, "DEF": 50, "SPD": 28}
    },
    {
        "name": "Adeline Sienna",
        "grand_title": "Golden Herald of the Dawn's Promise",
        "echo_titles": ["Sunflare Chorus of Renewed Hope", "Echo Radiance of Morning's Veil"],
        "stats": {"HP": 135, "ATK": 50, "DEF": 40, "SPD": 35}
    },
    {
        "name": "Melline Lien",
        "grand_title": "Verdant Matriarch of the Whispering Grove",
        "echo_titles": ["Emerald Hymn of Nature's Veil", "Echo Blossom of Gentle Renewal"],
        "stats": {"HP": 130, "ATK": 30, "DEF": 45, "SPD": 40}
    },
    {
        "name": "Serennia Verona",
        "grand_title": "Sable Oracle of the Shattered Star",
        "echo_titles": ["Midnight Prophecy of Cosmic Threads", "Echo Veil of Celestial Ruin"],
        "stats": {"HP": 110, "ATK": 45, "DEF": 35, "SPD": 50}
    },
    {
        "name": "Frida Nitterin",
        "grand_title": "Ivory Artisan of the Frostbound Tapestry",
        "echo_titles": ["Glacial Weave of Frozen Memory", "Echo Stitch of Winter's Grace"],
        "stats": {"HP": 125, "ATK": 25, "DEF": 50, "SPD": 30}
    },
    {
        "name": "Julie Blackwing",
        "grand_title": "Obsidian Valkyrie of the Eternal Oath",
        "echo_titles": ["Nightfall Echo of Unyielding Pledge", "Shadowstrike of Endless Duty"],
        "stats": {"HP": 150, "ATK": 48, "DEF": 42, "SPD": 25}
    },
    {
        "name": "Amelia Blackwing",
        "grand_title": "Onyx Sentinel of the Silent Horizon",
        "echo_titles": ["Echo Gaze of Distant Watch", "Ravenwing Pulse of Unseen Vigil"],
        "stats": {"HP": 140, "ATK": 28, "DEF": 50, "SPD": 40}
    },
    {
        "name": "Donnie Sienna",
        "grand_title": "Crimson Vanguard of the Blazing March",
        "echo_titles": ["Echo Rally of Fiery Courage", "Flareblade of Resolute Fire"],
        "stats": {"HP": 115, "ATK": 50, "DEF": 30, "SPD": 45}
    },
    {
        "name": "Dave Verona",
        "grand_title": "Twilight Strategist of the Fading Realm",
        "echo_titles": ["Duskweaver of Silent Calculus", "Echo Labyrinth of Waning Wits"],
        "stats": {"HP": 130, "ATK": 35, "DEF": 40, "SPD": 35}
    },
    {
        "name": "Felix Dory",
        "grand_title": "Azure Mariner of the Infinite Current",
        "echo_titles": ["Tidal Echo of Boundless Depths", "Wavehand of Eternal Voyage"],
        "stats": {"HP": 120, "ATK": 40, "DEF": 25, "SPD": 50}
    },
    {
        "name": "Scott Lien",
        "grand_title": "Verdant Sentry of the Living Rampart",
        "echo_titles": ["Echo Bastion of Rooted Resolve", "Leafguard of Perennial Stand"],
        "stats": {"HP": 145, "ATK": 30, "DEF": 45, "SPD": 28}
    },
    {
        "name": "Mirin Vienna",
        "grand_title": "Silver Architect of the Crystal Mosaic",
        "echo_titles": ["Prism Echo of Sacred Fragments", "Shardweave of Celestial Order"],
        "stats": {"HP": 135, "ATK": 45, "DEF": 30, "SPD": 40}
    },
    {
        "name": "Michael Smith",
        "grand_title": "Iron Paladin of the Unbreakable Light",
        "echo_titles": ["Lumina Echo of Unfaltering Will", "Shieldbrand of Radiant Defiance"],
        "stats": {"HP": 150, "ATK": 38, "DEF": 50, "SPD": 25}
    },
    {
        "name": "Carllen Vienna",
        "grand_title": "Glass Conductor of the Symphony's Edge",
        "echo_titles": ["Echo Crescendo of Shattered Melody", "Crystal Chord of Resounding Fate"],
        "stats": {"HP": 125, "ATK": 30, "DEF": 42, "SPD": 35}
    },
    {
        "name": "Kylian Sienna",
        "grand_title": "Emberblade Wanderer of the Wandering Flame",
        "echo_titles": ["Echo Ember of Roaming Sparks", "Firetrail of Restless Heart"],
        "stats": {"HP": 110, "ATK": 50, "DEF": 28, "SPD": 45}
    }
    ],
"Iridion": [
    {
        "name": "Kawakami Azou",
        "grand_title": "Silver Sage of the Ethereal Cascade",
        "echo_titles": ["Mistwhisper of Timeless Depth", "Echo Torrent of Quiet Wisdom"],
        "stats": {"HP": 130, "ATK": 35, "DEF": 45, "SPD": 30}
    },
    {
        "name": "Alice Azou",
        "grand_title": "Crystal Muse of the Northern Light",
        "echo_titles": ["Aurora Echo of Gentle Spark", "Prismdance of Silent Hymn"],
        "stats": {"HP": 145, "ATK": 40, "DEF": 35, "SPD": 45}
    },
    {
        "name": "Kitsune Linne",
        "grand_title": "Foxfire Rogue of the Veiled Mirage",
        "echo_titles": ["Illusion Echo of Shifting Veils", "Vulpine Waltz of Phantom Grace"],
        "stats": {"HP": 120, "ATK": 50, "DEF": 28, "SPD": 50}
    },
    {
        "name": "Mitsura Linne",
        "grand_title": "Jade Chrysalis of the Hidden Bloom",
        "echo_titles": ["Petal Echo of Secret Renewal", "Leafshade of Quiet Emergence"],
        "stats": {"HP": 135, "ATK": 30, "DEF": 50, "SPD": 40}
    },
    {
        "name": "Aika Miura",
        "grand_title": "Silver Archer of the Moonlit Vale",
        "echo_titles": ["Lunar Echo of Starlit Arrow", "Bowstring of Midnight Resolve"],
        "stats": {"HP": 110, "ATK": 45, "DEF": 25, "SPD": 35}
    },
    {
        "name": "Ruby Phoenix",
        "grand_title": "Crimson Rebirth of the Ashen Sky",
        "echo_titles": ["Flare Echo of Everlasting Rise", "Emberwing of Undying Hope"],
        "stats": {"HP": 150, "ATK": 50, "DEF": 40, "SPD": 30}
    },
    {
        "name": "Mynn Kanashi",
        "grand_title": "Obsidian Flame of the Shattered Frontier",
        "echo_titles": ["Blaze Echo of Forged Resolve", "Charcore of Unbroken Will"],
        "stats": {"HP": 125, "ATK": 35, "DEF": 45, "SPD": 28}
    },
    {
        "name": "Chiyo Kanashi",
        "grand_title": "Onyx Whisper of the Midnight Bloom",
        "echo_titles": ["Petal Echo of Silent Shadows", "Moonshard of Hidden Grace"],
        "stats": {"HP": 140, "ATK": 28, "DEF": 50, "SPD": 40}
    },
    {
        "name": "Lancy Azou",
        "grand_title": "Steel Duelist of the Celestial Forge",
        "echo_titles": ["Hammer Echo of Starforged Justice", "Anvilbrand of Cosmic Will"],
        "stats": {"HP": 130, "ATK": 50, "DEF": 30, "SPD": 45}
    },
    {
        "name": "Oliver Miura",
        "grand_title": "Verdant Blade of the Endless Thicket",
        "echo_titles": ["Vine Echo of Bound Growth", "Thornsong of Rooted Protection"],
        "stats": {"HP": 145, "ATK": 35, "DEF": 45, "SPD": 25}
    },
    {
        "name": "Keiko Denare",
        "grand_title": "Amber Inquisitor of the Sunken Archive",
        "echo_titles": ["Scroll Echo of Lost Lore", "Torchlight of Hidden Truths"],
        "stats": {"HP": 115, "ATK": 40, "DEF": 35, "SPD": 50}
    },
    {
        "name": "Akeno Blackwing",
        "grand_title": "Nightflare Assassin of the Silent Oath",
        "echo_titles": ["Shadow Echo of Unseen Strike", "Ravencloak of Hidden Vengeance"],
        "stats": {"HP": 150, "ATK": 45, "DEF": 38, "SPD": 30}
    },
    {
        "name": "Adriel Blackwing",
        "grand_title": "Obsidian Bard of the Ebon Lament",
        "echo_titles": ["Dirge Echo of Midnight Sorrow", "Wingbeat of Endless Remorse"],
        "stats": {"HP": 135, "ATK": 30, "DEF": 50, "SPD": 40}
    },
    {
        "name": "Brian Azou",
        "grand_title": "Bronze Architect of the Fractured Spire",
        "echo_titles": ["Echo Column of Shattered Symmetry", "Pillarbrand of Unfinished Dreams"],
        "stats": {"HP": 125, "ATK": 50, "DEF": 25, "SPD": 45}
    },
    {
        "name": "Matthew Habsburg",
        "grand_title": "Gilded Scion of the Imperial Veil",
        "echo_titles": ["Crown Echo of Hidden Dominion", "Scepterburst of Covert Sovereignty"],
        "stats": {"HP": 140, "ATK": 35, "DEF": 45, "SPD": 28}
    },
    {
        "name": "Lyon Sienna",
        "grand_title": "Scarlet Duelist of the Forsaken Arena",
        "echo_titles": ["Blade Echo of Bloodied Vow", "Arenaheart of Unyielding Grit"],
        "stats": {"HP": 120, "ATK": 45, "DEF": 30, "SPD": 50}
    }
    ],
    "Rosarium": [
    {
        "name": "Clara Melo",
        "grand_title": "Flame Artisan of the Threaded Lyric",
        "echo_titles": ["Emberdraft Sonata", "Smoldering Twist of Faith"],
        "stats": {"HP": 110, "ATK": 50, "DEF": 25, "SPD": 45}
    },
    {
        "name": "Ryan Ribeiro",
        "grand_title": "Conductor of the Sundering Pulse",
        "echo_titles": ["Harmonic Edge of the Fractured Signal", "Threnody of the Stormbound Chamber"],
        "stats": {"HP": 140, "ATK": 35, "DEF": 45, "SPD": 30}
    },
    {
        "name": "Elali Silva",
        "grand_title": "Oracle of the Tidal Loom",
        "echo_titles": ["Wavebraid Gospel of the Moonspun Thread", "Surgebound Whisper of the Abyssal Tide"],
        "stats": {"HP": 125, "ATK": 30, "DEF": 50, "SPD": 35}
    },
    {
        "name": "Iury Barbosa",
        "grand_title": "Envoy of the Broken Sigil",
        "echo_titles": ["Runeshard Testament of the Crimson Pact", "Vestige-Stitched Memory of the Pale Rift"],
        "stats": {"HP": 130, "ATK": 45, "DEF": 30, "SPD": 40}
    },
    {
        "name": "Gabrielly Aschley",
        "grand_title": "Votary of the Rose-Split Oath",
        "echo_titles": ["Bloomscript Verse of the Vowkeeper's Wake", "Sanguine Devotion of the Petalshard Faith"],
        "stats": {"HP": 115, "ATK": 40, "DEF": 35, "SPD": 45}
    },
    {
        "name": "Iuri Antonio",
        "grand_title": "Herald of the Hollow Meridian",
        "echo_titles": ["Chime of the Forgotten Hemispheres", "Orbit-Stilled Murmur of the Rift"],
        "stats": {"HP": 150, "ATK": 30, "DEF": 50, "SPD": 28}
    },
    {
        "name": "Thaynara Magno",
        "grand_title": "Luminary of the Woven Morrow",
        "echo_titles": ["Veilthread Vision of the Seraph's Gate", "Emberlace Hymn of the Yetborn Dawn"],
        "stats": {"HP": 135, "ATK": 25, "DEF": 45, "SPD": 40}
    },
    {
        "name": "William Torres",
        "grand_title": "Cipherwright of the Obsidian Crucible",
        "echo_titles": ["Forgebound Whisper of the Last Theorem", "Shattercoil Sigil of the Molten Word"],
        "stats": {"HP": 120, "ATK": 45, "DEF": 40, "SPD": 35}
    },
    {
        "name": "Lara Pontes",
        "grand_title": "Cartographer of the Gentle Abyss",
        "echo_titles": ["Maptide Lullaby of the Sunken Grace", "Trace of the Pale Horizon's Sleep"],
        "stats": {"HP": 110, "ATK": 30, "DEF": 35, "SPD": 50}
    },
    {
        "name": "Ivanildo Camilo",
        "grand_title": "Vigilkeeper of the Blazing Psalm",
        "echo_titles": ["Lanternborn Litany of the Ember Choir", "Ashscribed Rite of the Faithful Flame"],
        "stats": {"HP": 145, "ATK": 50, "DEF": 25, "SPD": 30}
    },
    {
        "name": "Jandira Lopes",
        "grand_title": "Matron of the Withered Harvest",
        "echo_titles": ["Silkblood Chant of the Autumn Veil", "Covenant of the Crumbling Root"],
        "stats": {"HP": 130, "ATK": 35, "DEF": 45, "SPD": 28}
    },
    {
        "name": "Mickael Ribeiro",
        "grand_title": "Stormbinder of the Resonant Wake",
        "echo_titles": ["Pulse-scripted Ode of the Thundering Seal", "Echocast Pledge of the Fractured Sky"],
        "stats": {"HP": 125, "ATK": 50, "DEF": 30, "SPD": 40}
    },
    {
        "name": "Jhennifer Kelly",
        "grand_title": "Seeker of the Unfurled Echo",
        "echo_titles": ["Miragewoven Dream of the Hollow Choir", "Threads of the Dawn-Split Memory"],
        "stats": {"HP": 140, "ATK": 30, "DEF": 50, "SPD": 35}
    },
    {
        "name": "Vinicius Figueira",
        "grand_title": "Thornscribe of the Silver Grove",
        "echo_titles": ["Runebound Pact of the Verdant Eclipse", "Scrawl of the Twilight Root"],
        "stats": {"HP": 135, "ATK": 45, "DEF": 28, "SPD": 45}
    },
    {
        "name": "Sophia Paulino",
        "grand_title": "Warden of the Blooming Silence",
        "echo_titles": ["Petalwoven Verse of Dusk", "Whispers Beneath the Veil of Wind"],
        "stats": {"HP": 115, "ATK": 25, "DEF": 40, "SPD": 50}
    },
    {
        "name": "Vinicius Alves",
        "grand_title": "Archivist of Guttered Light",
        "echo_titles": ["Flickerbound Oath of the Forgotten Flame", "Ledger of the Ashen Truth"],
        "stats": {"HP": 150, "ATK": 40, "DEF": 35, "SPD": 25}
    }
    ],
"Olive": [
    {
        "name": "Reddo Satoshi",
        "grand_title": "Warden of the Silent Apex",
        "echo_titles": ["Summitbound Reverie of the Vanished Word", "Echo of the Patched Silence"],
        "stats": {"HP": 120, "ATK": 35, "DEF": 45, "SPD": 30}
    },
    {
        "name": "Benjamin Tennyson",
        "grand_title": "Heir to the Living Glyph",
        "echo_titles": ["Sigilscript Canticle of the Turning Veil", "Trialshard of the Tenfold Bloom"],
        "stats": {"HP": 150, "ATK": 50, "DEF": 40, "SPD": 25}
    },
    {
        "name": "John Doe",
        "grand_title": "Cipher of the Unnamed Wake",
        "echo_titles": ["Glitchbound Whisper of the Forgotten Root", "Anonbound Liturgy of the Broken Login"],
        "stats": {"HP": 110, "ATK": 30, "DEF": 35, "SPD": 50}
    },
    {
        "name": "Ajax Tartaglia",
        "grand_title": "Bearer of the Depthbound Oath",
        "echo_titles": ["Crimsonwave Testament of the Shifting Tide", "Echo of the Mirrored Blade"],
        "stats": {"HP": 140, "ATK": 45, "DEF": 30, "SPD": 35}
    },
    {
        "name": "Gary Oak",
        "grand_title": "Archivist of Verdant Inheritance",
        "echo_titles": ["Leafscript Verse of the Legacy Duel", "Palletborne Chronicle of the Grown Seed"],
        "stats": {"HP": 135, "ATK": 30, "DEF": 50, "SPD": 28}
    },
    {
        "name": "Satoru Gojo",
        "grand_title": "Watcher of the Hollow Threshold",
        "echo_titles": ["Veilbound Oath of the Silent Realm", "Sixfold Verse of the Unseen Horizon"],
        "stats": {"HP": 145, "ATK": 50, "DEF": 25, "SPD": 30}
    },
    {
        "name": "Kaedehara Kazuha",
        "grand_title": "Wanderer of the Windswept Lament",
        "echo_titles": ["Leafsong Gospel of the Autumn Path", "Haikubound Whisper of the Distant Pulse"],
        "stats": {"HP": 130, "ATK": 40, "DEF": 28, "SPD": 50}
    },
    {
        "name": "Diluc Ragnvindr",
        "grand_title": "Keeper of the Emberfast Wake",
        "echo_titles": ["Winewrought Liturgy of the Vigil Flame", "Redcrest Vow of the Shrouded Vigilant"],
        "stats": {"HP": 150, "ATK": 50, "DEF": 35, "SPD": 25}
    },
    {
        "name": "Lusamine Mohn",
        "grand_title": "Curator of the Fractured Bloom",
        "echo_titles": ["Petalbound Oath of the Hollow Aurora", "Gospel of the Ultralight Garden"],
        "stats": {"HP": 125, "ATK": 30, "DEF": 45, "SPD": 40}
    },
    {
        "name": "Kasane Teto",
        "grand_title": "Chimera of the Spiraltongue Hymn",
        "echo_titles": ["Scriptwoven Canticle of the Dual Thread", "Mirrorsong Verse of the Synthetic Bloom"],
        "stats": {"HP": 115, "ATK": 45, "DEF": 25, "SPD": 50}
    },
    {
        "name": "Miku Hatsune",
        "grand_title": "Voice of the Luminous Pattern",
        "echo_titles": ["Neonbound Aria of the Refracted Dream", "Synthwoven Echo of the First Sound"],
        "stats": {"HP": 140, "ATK": 25, "DEF": 40, "SPD": 45}
    },
    {
        "name": "Cynthia Shirona",
        "grand_title": "Champion of the Celestial Accord",
        "echo_titles": ["Mythscript Verse of the Twilight Crest", "Lineagebound Echo of the Lunar Gate"],
        "stats": {"HP": 135, "ATK": 35, "DEF": 45, "SPD": 30}
    },
    {
        "name": "Rosalyne Lohefalter",
        "grand_title": "Consort of the Quiet Ember",
        "echo_titles": ["Frostgilded Elegy of the Veiled Flame", "Ashenbound Vow of the Crimson Night"],
        "stats": {"HP": 110, "ATK": 50, "DEF": 30, "SPD": 40}
    },
    {
        "name": "Tomoe Mami",
        "grand_title": "Sentinel of the Blooming Ribbon",
        "echo_titles": ["Tirobound Whisper of the Gracebound Sigil", "Tea-Laced Hymn of the Solitary Bloom"],
        "stats": {"HP": 130, "ATK": 25, "DEF": 50, "SPD": 35}
    },
    {
        "name": "Jean Gunnhildr",
        "grand_title": "Falcon of the Enduring Watch",
        "echo_titles": ["Windscript Gospel of the Tireless Accord", "Canticle of the Dawnfold Vow"],
        "stats": {"HP": 145, "ATK": 40, "DEF": 28, "SPD": 50}
    },
    {
        "name": "Navia Caspar",
        "grand_title": "President of the Rosette Archive",
        "echo_titles": ["Casparbound Liturgy of the Shattered Crest", "Gunpetal Verse of the Gilded Mourning"],
        "stats": {"HP": 125, "ATK": 45, "DEF": 35, "SPD": 25}
    }
]
}

EchoTitles = [
  {
    "title": "Bulwark of Chosen Torment",
    "effect_type": [
      "damage_negation",
      "def_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 15,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Emptiness's Herald",
    "effect_type": [
      "def_buff",
      "debuff_removal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 20,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Harbinger of Hollow Resolve",
    "effect_type": [
      "debuff_removal",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Bond of Returned Burdens",
    "effect_type": [
      "damage_negation",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -5,
      "SPD": 0,
      "HP": 15,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Mirrorcrack Echo",
    "effect_type": [
      "status_immunity",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Smile of Regretted Echo",
    "effect_type": [
      "reflect",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Script of Twisted Reflections",
    "effect_type": [
      "status_immunity",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Warden of Fallen Vanity",
    "effect_type": [
      "status_immunity",
      "ally_protection"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Weaver of Final Severance",
    "effect_type": [
      "reflect",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Petals of Parting Unity",
    "effect_type": [
      "ally_protection",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 0,
      "HP": 25,
      "EP": 5
    },
    "ep_cost": 75
  },
  {
    "title": "Keeper of Fragile Lucidity",
    "effect_type": [
      "ally_protection",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 15,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Architect of War Dreams",
    "effect_type": [
      "ally_protection",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": -2,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Testimony of Blooded Teachings",
    "effect_type": [
      "burst",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Song of Enduring Reality",
    "effect_type": [
      "ally_protection",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 0,
      "HP": 25,
      "EP": 5
    },
    "ep_cost": 75
  },
  {
    "title": "Ray of Unbowed Heritage",
    "effect_type": [
      "ally_protection",
      "reflect"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Blade of Uncertain Truths",
    "effect_type": [
      "bonus_damage",
      "status_immunity"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": -2,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Rhyme of Unbent Conviction",
    "effect_type": [
      "def_buff",
      "ally_protection"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 0,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Artisan of Final Creation",
    "effect_type": [
      "spd_buff",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 4,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Echoes of Carved Lessons",
    "effect_type": [
      "debuff_removal",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Geode Vow Ascendant",
    "effect_type": [
      "heal",
      "ally_protection"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": -2,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Soulstrike in Hollow Skies",
    "effect_type": [
      "bonus_damage",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 8,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Piercing Spirit Blitz",
    "effect_type": [
      "spd_buff",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 0,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Huntress of the Shattered Bloom",
    "effect_type": [
      "ep_gain",
      "atk_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 0,
      "HP": 5,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Stampede of the Bitter Creed",
    "effect_type": [
      "bonus_damage",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 6,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Last Gift Eruption",
    "effect_type": [
      "spd_buff",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Riftstorm Crescendo",
    "effect_type": [
      "burst",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Tidesurge Spiral",
    "effect_type": [
      "spd_buff",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Aqua Vortex Waltz",
    "effect_type": [
      "heal",
      "ally_protection"
    ],
    "target_type": "ally_aoe",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Heroic Echo of the Tiny Titan",
    "effect_type": [
      "status_immunity",
      "ally_protection"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 8,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Misfortune's Gambitblade",
    "effect_type": [
      "bonus_damage",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Letterblade of Silent Catharsis",
    "effect_type": [
      "ally_protection",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 0,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Elder Blood Surge of the Echo Rift",
    "effect_type": [
      "spd_buff",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Ghostthread of Echo Synchrony",
    "effect_type": [
      "ally_protection",
      "spd_buff"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 8,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Stellar Requiem of Silent Knowing",
    "effect_type": [
      "spd_buff",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Featherspell of the Fading Sky",
    "effect_type": [
      "atk_buff",
      "heal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 0,
      "HP": 10,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Goldseal Transmutation of Echo Guilt",
    "effect_type": [
      "buff_removal",
      "damage_negation"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 5,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Bastion of Unbroken Vow",
    "effect_type": [
      "ally_protection",
      "reflect"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 5,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Radiance of Morning's Veil",
    "effect_type": [
      "debuff_removal",
      "ally_protection"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Glacial Weave of Frozen Memory",
    "effect_type": [
      "reflect",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Stitch of Winter's Grace",
    "effect_type": [
      "heal",
      "ally_protection"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 0,
      "HP": 25,
      "EP": 5
    },
    "ep_cost": 75
  },
  {
    "title": "Shadowstrike of Endless Duty",
    "effect_type": [
      "bonus_damage",
      "def_ignore"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 0,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Echo Rally of Fiery Courage",
    "effect_type": [
      "status_immunity",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": -2,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Flareblade of Resolute Fire",
    "effect_type": [
      "bonus_damage",
      "spd_buff"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Echo Bastion of Rooted Resolve",
    "effect_type": [
      "ally_protection",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Leafguard of Perennial Stand",
    "effect_type": [
      "heal",
      "reflect"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Shardweave of Celestial Order",
    "effect_type": [
      "cloak",
      "ally_protection"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Shieldbrand of Radiant Defiance",
    "effect_type": [
      "ally_protection",
      "reflect"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Firetrail of Restless Heart",
    "effect_type": [
      "atk_buff",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Aurora Echo of Gentle Spark",
    "effect_type": [
      "spd_buff",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 2,
      "SPD": 10,
      "HP": 10,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Leafshade of Quiet Emergence",
    "effect_type": [
      "ally_protection",
      "buff_removal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Emberwing of Undying Hope",
    "effect_type": [
      "spd_buff",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 4,
      "SPD": 5,
      "HP": 10,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Anvilbrand of Cosmic Will",
    "effect_type": [
      "burst",
      "ally_protection"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 0,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Scroll Echo of Lost Lore",
    "effect_type": [
      "spd_buff",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 85
  },
  {
    "title": "Ravencloak of Hidden Vengeance",
    "effect_type": [
      "bonus_damage",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": 0,
      "SPD": 5,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Wingbeat of Endless Remorse",
    "effect_type": [
      "revive",
      "ally_protection"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Column of Shattered Symmetry",
    "effect_type": [
      "status_immunity",
      "atk_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 2,
      "SPD": 5,
      "HP": 10,
      "EP": 10
    },
    "ep_cost": 95
  },
  {
    "title": "Emberdraft Sonata",
    "effect_type": [
      "atk_buff",
      "spd_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 5,
      "SPD": 10,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Harmonic Edge of the Fractured Signal",
    "effect_type": [
      "aoe_damage",
      "def_ignore"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Surgebound Whisper of the Abyssal Tide",
    "effect_type": [
      "atk_buff",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 5,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Runeshard Testament of the Crimson Pact",
    "effect_type": [
      "burn",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Vestige-Stitched Memory of the Pale Rift",
    "effect_type": [
      "revive",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 0,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Sanguine Devotion of the Petalshard Faith",
    "effect_type": [
      "lifesteal",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Chime of the Forgotten Hemispheres",
    "effect_type": [
      "def_buff",
      "freeze"
    ],
    "target_type": "aoe_enemy",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 15,
      "SPD": 0,
      "HP": 20,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Orbit-Stilled Murmur of the Rift",
    "effect_type": [
      "atk_buff",
      "def_ignore"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Emberlace Hymn of the Yetborn Dawn",
    "effect_type": [
      "heal",
      "regen"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 5,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Forgebound Whisper of the Last Theorem",
    "effect_type": [
      "burst",
      "shield"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Shattercoil Sigil of the Molten Word",
    "effect_type": [
      "bonus_damage",
      "burn"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Maptide Lullaby of the Sunken Grace",
    "effect_type": [
      "slow",
      "heal"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 3,
      "SPD": 15,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 75
  },
  {
    "title": "Trace of the Pale Horizon's Sleep",
    "effect_type": [
      "dodge",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 75
  },
  {
    "title": "Ashscribed Rite of the Faithful Flame",
    "effect_type": [
      "revive",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 2,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 75
  },
  {
    "title": "Covenant of the Crumbling Root",
    "effect_type": [
      "slow",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 15,
      "SPD": -5,
      "HP": 10,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Pulse-scripted Ode of the Thundering Seal",
    "effect_type": [
      "aoe_damage",
      "stun"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Echocast Pledge of the Fractured Sky",
    "effect_type": [
      "atk_buff",
      "def_buff"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 10,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Miragewoven Dream of the Hollow Choir",
    "effect_type": [
      "dodge",
      "heal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 8,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Threads of the Dawn-Split Memory",
    "effect_type": [
      "status_immunity",
      "atk_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": 2,
      "SPD": 3,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Runebound Pact of the Verdant Eclipse",
    "effect_type": [
      "taunt",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Scrawl of the Twilight Root",
    "effect_type": [
      "lifesteal",
      "def_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Petalwoven Verse of Dusk",
    "effect_type": [
      "regen",
      "heal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 4,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Whispers Beneath the Veil of Wind",
    "effect_type": [
      "cloak",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Ledger of the Ashen Truth",
    "effect_type": [
      "burst",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 15,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Summitbound Reverie of the Vanished Word",
    "effect_type": [
      "reflect",
      "silence"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 0,
      "HP": 5,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Echo of the Patched Silence",
    "effect_type": [
      "dodge",
      "def_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 8,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Sigilscript Canticle of the Turning Veil",
    "effect_type": [
      "revive",
      "cloak"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": 3,
      "SPD": -5,
      "HP": 20,
      "EP": -10
    },
    "ep_cost": 95
  },
  {
    "title": "Trialshard of the Tenfold Bloom",
    "effect_type": [
      "atk_buff",
      "def_buff"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 5,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Glitchbound Whisper of the Forgotten Root",
    "effect_type": [
      "burst",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Anonbound Liturgy of the Broken Login",
    "effect_type": [
      "cloak",
      "stun"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Crimsonwave Testament of the Shifting Tide",
    "effect_type": [
      "aoe_damage",
      "burn"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Echo of the Mirrored Blade",
    "effect_type": [
      "reflect",
      "def_ignore"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Leafscript Verse of the Legacy Duel",
    "effect_type": [
      "atk_buff",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 5,
      "SPD": 0,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Veilbound Oath of the Silent Realm",
    "effect_type": [
      "status_immunity",
      "freeze"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Sixfold Verse of the Unseen Horizon",
    "effect_type": [
      "atk_buff",
      "def_buff"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 95
  },
  {
    "title": "Leafsong Gospel of the Autumn Path",
    "effect_type": [
      "cloak",
      "atk_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Haikubound Whisper of the Distant Pulse",
    "effect_type": [
      "burst",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Neonbound Aria of the Refracted Dream",
    "effect_type": [
      "def_buff",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 10,
      "SPD": 15,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Pyreborn Testament",
    "effect_type": [
      "shield",
      "aoe_damage"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 5,
      "SPD": -5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Ember's Final Whisper",
    "effect_type": [
      "revive",
      "taunt"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 0,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Tethered Echostep",
    "effect_type": [
      "atk_buff",
      "ep_gain"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Bloom of Shared Wanderings",
    "effect_type": [
      "heal",
      "spd_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 7,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 75
  },
  {
    "title": "Vestige of Silent Rage",
    "effect_type": [
      "damage_negation",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 8,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Vigil of Broken Honor",
    "effect_type": [
      "def_buff",
      "status_immunity"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Plaguebearer of Fevered Ambitions",
    "effect_type": [
      "dot",
      "debuff"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": -5,
      "HP": -20,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Bane of Trembling Courage",
    "effect_type": [
      "bonus_damage",
      "burn"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": -5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Rampart of Welcomed Oblivion",
    "effect_type": [
      "def_buff",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": -10,
      "DEF": 20,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Guide of Beyond Regret",
    "effect_type": [
      "status_immunity",
      "ally_protection"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Waltz of Rediscovered Rhythms",
    "effect_type": [
      "spd_buff",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 80
  },
  {
    "title": "Forge of Unyielding Belief",
    "effect_type": [
      "def_buff",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Sentinel of Bending Truths",
    "effect_type": [
      "dodge",
      "buff_removal"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 2,
      "SPD": 3,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Murmur of Broken Hopes",
    "effect_type": [
      "taunt",
      "buff_removal"
    ],
    "target_type": "aoe_enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": -10
    },
    "ep_cost": 80
  },
  {
    "title": "Legend of Silent Sorrow",
    "effect_type": [
      "revive",
      "damage_negation"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 0,
      "HP": 30,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Chorus of Broken Hope",
    "effect_type": [
      "atk_buff",
      "debuff_removal"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": -10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Lament of Fading Trust",
    "effect_type": [
      "debuff",
      "status_immunity"
    ],
    "target_type": "aoe_enemy",
    "stat_modifiers": {
      "ATK": -15,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Burdenbearer's Final Stand",
    "effect_type": [
      "taunt",
      "def_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 15,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Bloodwritten Oath",
    "effect_type": [
      "bonus_damage",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -5,
      "SPD": -5,
      "HP": -5,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Pupil of Crimson Betrayal",
    "effect_type": [
      "atk_buff",
      "spd_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Trailblazer of Unholy Power",
    "effect_type": [
      "def_ignore",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -10,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Chorus of Mended Bonds",
    "effect_type": [
      "ep_gain",
      "debuff_removal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 80
  },
  {
    "title": "Verse of Parting Joy",
    "effect_type": [
      "heal",
      "spd_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 15,
      "HP": 25,
      "EP": 0
    },
    "ep_cost": 70
  },
  {
    "title": "Surface Whispers of Passage",
    "effect_type": [
      "spd_buff",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 15,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Tide of Unheard Ballads",
    "effect_type": [
      "debuff",
      "bonus_damage"
    ],
    "target_type": "aoe_enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": -10
    },
    "ep_cost": 90
  },
  {
    "title": "Silencebreak's Critic",
    "effect_type": [
      "silence",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 2,
      "DEF": -5,
      "SPD": 2,
      "HP": -5,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Laughter's Final Bane",
    "effect_type": [
      "stun",
      "buff_removal"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Baptizer of Burning Anger",
    "effect_type": [
      "regen",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Flame of Unquenchable Hate",
    "effect_type": [
      "burn",
      "silence"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 0,
      "HP": -10,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Dreamwright's Rebirth",
    "effect_type": [
      "revive",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Beacon of New Ruins",
    "effect_type": [
      "debuff_removal",
      "status_immunity"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Shield of Shattered Promises",
    "effect_type": [
      "shield",
      "def_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 3,
      "SPD": -5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Maiden of Regret's Dawn",
    "effect_type": [
      "status_immunity",
      "heal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -5,
      "SPD": 2,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Breath of Bound Fate",
    "effect_type": [
      "ally_protection",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -5,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 80
  },
  {
    "title": "Cipher of Unbroken Threads",
    "effect_type": [
      "dodge",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Petal of Fraying Hope",
    "effect_type": [
      "heal",
      "damage_negation"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": -2,
      "DEF": 0,
      "SPD": 0,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Whisper of Fading Tethers",
    "effect_type": [
      "spd_buff",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Defender of Born Legacies",
    "effect_type": [
      "damage_negation",
      "def_buff"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 4,
      "SPD": -5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Pathcarver of Fleeting Honors",
    "effect_type": [
      "def_buff",
      "buff_removal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Quill of Untold Saga",
    "effect_type": [
      "ep_gain",
      "debuff_removal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Blade of Renewed Ruin",
    "effect_type": [
      "burst",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 3,
      "DEF": -5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Rhythm of Missed Steps",
    "effect_type": [
      "cloak",
      "spd_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -8,
      "SPD": 15,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Echo of Unwalked Paths",
    "effect_type": [
      "dodge",
      "spd_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Death's Curiosity Catalyst",
    "effect_type": [
      "atk_buff",
      "damage_negation"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -5,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Slayer of Unasked Questions",
    "effect_type": [
      "burst",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Knuckles of Vengeful Pardon",
    "effect_type": [
      "bonus_damage",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": -5,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Echo of Applause Lost",
    "effect_type": [
      "ep_gain",
      "cloak"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Reflection of Hollow Cheers",
    "effect_type": [
      "status_immunity",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 5,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Step of the Untraced Night",
    "effect_type": [
      "cloak",
      "dodge"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Chord of Forgotten Starlight",
    "effect_type": [
      "spd_buff",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Splinter of True Reflection",
    "effect_type": [
      "regen",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Whisper of Shattered Glory",
    "effect_type": [
      "burst",
      "def_ignore"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Remnant of Fallen Triumph",
    "effect_type": [
      "revive",
      "status_immunity"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": -2,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Dancer of War's Lullaby",
    "effect_type": [
      "cloak",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Weaver of Nightmare Steps",
    "effect_type": [
      "cloak",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Carver of Vengeance Scars",
    "effect_type": [
      "bonus_damage",
      "status_immunity"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Scrawl of Unyielding Wrath",
    "effect_type": [
      "ep_gain",
      "def_ignore"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Reflection of Loud Regrets",
    "effect_type": [
      "cloak",
      "spd_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Sculptor of Rising Ashes",
    "effect_type": [
      "revive",
      "ep_gain"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 5,
      "HP": 15,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Tide of Messy Genesis",
    "effect_type": [
      "reflect",
      "ally_protection"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": -5,
      "DEF": 5,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Virus of Perfect Lies",
    "effect_type": [
      "cloak",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Muse of Forgotten Alms",
    "effect_type": [
      "heal",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -3,
      "SPD": 0,
      "HP": 20,
      "EP": 10
    },
    "ep_cost": 80
  },
  {
    "title": "Shadow of Vanished Love",
    "effect_type": [
      "cloak",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Blade of Faith Unmade",
    "effect_type": [
      "def_ignore",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Narrator of Reborn Tales",
    "effect_type": [
      "debuff_removal",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Scarlet of Ruin's Renewal",
    "effect_type": [
      "revive",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": -2,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Threadsnare Unraveled",
    "effect_type": [
      "reflect",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Motionbound Liberation",
    "effect_type": [
      "dodge",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Penitent's Unspoken Cries",
    "effect_type": [
      "burn",
      "bonus_damage"
    ],
    "target_type": "aoe_enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Blade of Forgiven Silence",
    "effect_type": [
      "def_ignore",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": -2,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Mercy's Last Echo",
    "effect_type": [
      "heal",
      "debuff_removal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Shard of Fractured Devotion",
    "effect_type": [
      "cloak",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Tether of Last Grip",
    "effect_type": [
      "revive",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Echo of Sistered Laughter",
    "effect_type": [
      "reflect",
      "regen"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 15,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Fray of Farewell Mirth",
    "effect_type": [
      "cloak",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Roar of Unsilenced Sorrow",
    "effect_type": [
      "burst",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 5,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Requiem of the Broken Blade",
    "effect_type": [
      "revive",
      "reflect"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 0,
      "HP": 10,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Builder of Battlefield Echoes",
    "effect_type": [
      "status_immunity",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Veil of Vanishing Hopes",
    "effect_type": [
      "cloak",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Flame of Last Respite",
    "effect_type": [
      "heal",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Accusation in Crescendo",
    "effect_type": [
      "spd_buff",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Beacon of Unyielding Beauty",
    "effect_type": [
      "damage_negation",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Vanguard of Coveted Legacies",
    "effect_type": [
      "burst",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Shadow's Faith Wielder",
    "effect_type": [
      "cloak",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Vanity's Final Embrace",
    "effect_type": [
      "revive",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": -2,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Patch of Restored Truth",
    "effect_type": [
      "debuff_removal",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Echofixer of Fractured Voices",
    "effect_type": [
      "spd_buff",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Current of Silent Stories",
    "effect_type": [
      "cloak",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Melody of Hidden Longings",
    "effect_type": [
      "reflect",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Bard of Approaching End",
    "effect_type": [
      "shield",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Guide to Crimson Exits",
    "effect_type": [
      "cloak",
      "def_ignore"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Shatterbound Silhouette",
    "effect_type": [
      "reflect",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Fragment of Self-Sight",
    "effect_type": [
      "cloak",
      "spd_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Ruinforged Monument",
    "effect_type": [
      "taunt",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": -2,
      "SPD": 0,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Corpse-stitched Aspiration",
    "effect_type": [
      "revive",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Wraith of Stolen Vengeance",
    "effect_type": [
      "cloak",
      "bonus_damage"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Shadow of Reclaimed Will",
    "effect_type": [
      "dodge",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 80
  },
  {
    "title": "Edge of Curious Revelation",
    "effect_type": [
      "def_ignore",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Weave of Enduring Fears",
    "effect_type": [
      "lifesteal",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Ballad of True Pain",
    "effect_type": [
      "aoe_damage",
      "bonus_damage"
    ],
    "target_type": "aoe_enemy",
    "stat_modifiers": {
      "ATK": -5,
      "DEF": -3,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Antidote of Unshaken Will",
    "effect_type": [
      "ally_protection",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 0,
      "HP": 25,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Cure of Quivering Fears",
    "effect_type": [
      "debuff_removal",
      "ally_protection"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Echo of Lost Resolve",
    "effect_type": [
      "taunt",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 2,
      "SPD": 0,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Dirge of the Forgotten Oath",
    "effect_type": [
      "debuff",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Elegy of Tearborn Steel",
    "effect_type": [
      "burst",
      "aoe_damage"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Creation's Last Lament",
    "effect_type": [
      "revive",
      "burn"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 0,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Echo of Shattered Shields",
    "effect_type": [
      "def_ignore",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -5,
      "SPD": 5,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Conflagration's Masterpiece",
    "effect_type": [
      "burn",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Regretforged Pathwalker",
    "effect_type": [
      "status_immunity",
      "def_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 5,
      "SPD": 0,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Aria of Tidal Judgment",
    "effect_type": [
      "aoe_damage",
      "taunt"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": 2,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Saltborn Veilbreaker",
    "effect_type": [
      "debuff_removal",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Hammering Spiral of Grace",
    "effect_type": [
      "def_buff",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 0,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Winds of Lacerated Karma",
    "effect_type": [
      "burn",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Chronoblade Waltz",
    "effect_type": [
      "spd_buff",
      "damage_negation"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 15,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Bloom of Stasis Rift",
    "effect_type": [
      "status_immunity",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 2,
      "SPD": 10,
      "HP": 10,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Redshift Spark of Ruin",
    "effect_type": [
      "burn",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Glasswing Chaos Pulse",
    "effect_type": [
      "spd_buff",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 15,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Limitless Sunflare Drive",
    "effect_type": [
      "aoe_damage",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 14,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Atomic Chainbreaker Verdict",
    "effect_type": [
      "def_buff",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 8,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Rogue Bloom Rebellion",
    "effect_type": [
      "def_buff",
      "ally_protection"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 8,
      "SPD": 0,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Survivor of Reckoning's Shroud",
    "effect_type": [
      "cloak",
      "buff_removal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 5,
      "SPD": 5,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Silver Sentinel of the Undead Hour",
    "effect_type": [
      "status_immunity",
      "heal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 8,
      "SPD": 0,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Flamehair of the Fractured Code",
    "effect_type": [
      "burn",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Signs of Wolfblood Vow",
    "effect_type": [
      "def_ignore",
      "taunt"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": 2,
      "SPD": 0,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Blade of Twilit Reckoning",
    "effect_type": [
      "atk_buff",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 6,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Hollowshot Redemption",
    "effect_type": [
      "aoe_damage",
      "taunt"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 4,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Echoes Beneath Spores",
    "effect_type": [
      "spd_buff",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 10,
      "EP": 8
    },
    "ep_cost": 85
  },
  {
    "title": "Bullet Aria of Forgotten Grace",
    "effect_type": [
      "bonus_damage",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 5,
      "HP": 5,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Witchtime Waltz of Eternal Dusk",
    "effect_type": [
      "cloak",
      "damage_negation"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 10,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Rebellion Aria",
    "effect_type": [
      "burst",
      "aoe_damage"
    ],
    "target_type": "aoe_enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 0,
      "HP": 5,
      "EP": 10
    },
    "ep_cost": 95
  },
  {
    "title": "Judgment Cut Nocturne",
    "effect_type": [
      "def_ignore",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Hollow Flash Waltz",
    "effect_type": [
      "bonus_damage",
      "spd_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": 0,
      "SPD": 12,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 85
  },
  {
    "title": "Punch of Noble Folly",
    "effect_type": [
      "taunt",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 2,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Buster Blade of Memory's Rift",
    "effect_type": [
      "aoe_damage",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 14,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Meteorheart of the Fading Stream",
    "effect_type": [
      "status_immunity",
      "revive"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Velvet Schemer of the Hidden Veil",
    "effect_type": [
      "cloak",
      "spd_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Cryo Waltz of the Lost Lineage",
    "effect_type": [
      "freeze",
      "buff_removal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 2,
      "SPD": 5,
      "HP": 10,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Dragon Spark Halo",
    "effect_type": [
      "burn",
      "spd_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Pyroburst Petalstorm",
    "effect_type": [
      "burst",
      "aoe_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Trickster of Stolen Triumphs",
    "effect_type": [
      "cloak",
      "bonus_damage"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": 0,
      "SPD": 8,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Gilded Trigger of Emotion's Resurgence",
    "effect_type": [
      "ep_gain",
      "dodge"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 10,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Lionheart Echo of Noble Oaths",
    "effect_type": [
      "def_buff",
      "taunt"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 0,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 80
  },
  {
    "title": "Excalibur's Vowborne Radiance",
    "effect_type": [
      "burst",
      "bonus_damage"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Wild Huntbreaker of Ancestral Storms",
    "effect_type": [
      "ep_gain",
      "def_ignore"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 95
  },
  {
    "title": "Echo Aeon of Soft Sacrifice",
    "effect_type": [
      "heal",
      "def_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 8,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Faithwave of the Lunar Prayer",
    "effect_type": [
      "revive",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Neon Petal of Broken Futures",
    "effect_type": [
      "burn",
      "spd_buff"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Phantom of Silent Signalshine",
    "effect_type": [
      "cloak",
      "damage_negation"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Tactician's Mindforge of Memory Logic",
    "effect_type": [
      "ep_gain",
      "buff_removal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Spiral Lance of Blazing Psyche",
    "effect_type": [
      "burst",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Echoflare of Unyielding Brilliance",
    "effect_type": [
      "burst",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": 0,
      "SPD": 8,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Echo Pulse of the Eternal Child",
    "effect_type": [
      "buff_removal",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Moonfang Echo of Sorrow's Legacy",
    "effect_type": [
      "burst",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 2,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Gothblade of the Eternal Midnight",
    "effect_type": [
      "def_ignore",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 5,
      "SPD": 0,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Echo Drift of Heartshaped Chaos",
    "effect_type": [
      "cloak",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Soulbound Mechanist of the Lost Limb",
    "effect_type": [
      "status_immunity",
      "aoe_damage"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 2,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Silver Lullaby of Waning Dreams",
    "effect_type": [
      "dodge",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Echo Embrace of Night's Refrain",
    "effect_type": [
      "cloak",
      "heal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Crimson Ward of Silent Fortitude",
    "effect_type": [
      "status_immunity",
      "revive"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Sunflare Chorus of Renewed Hope",
    "effect_type": [
      "heal",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 0,
      "HP": 25,
      "EP": 10
    },
    "ep_cost": 75
  },
  {
    "title": "Emerald Hymn of Nature's Veil",
    "effect_type": [
      "cloak",
      "debuff_removal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Echo Blossom of Gentle Renewal",
    "effect_type": [
      "heal",
      "reflect"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Midnight Prophecy of Cosmic Threads",
    "effect_type": [
      "spd_buff",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Echo Veil of Celestial Ruin",
    "effect_type": [
      "cloak",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Nightfall Echo of Unyielding Pledge",
    "effect_type": [
      "revive",
      "atk_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 8,
      "DEF": -2,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Gaze of Distant Watch",
    "effect_type": [
      "spd_buff",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Ravenwing Pulse of Unseen Vigil",
    "effect_type": [
      "status_immunity",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Duskweaver of Silent Calculus",
    "effect_type": [
      "cloak",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Labyrinth of Waning Wits",
    "effect_type": [
      "spd_buff",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 85
  },
  {
    "title": "Tidal Echo of Boundless Depths",
    "effect_type": [
      "reflect",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Wavehand of Eternal Voyage",
    "effect_type": [
      "cloak",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Prism Echo of Sacred Fragments",
    "effect_type": [
      "atk_buff",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Lumina Echo of Unfaltering Will",
    "effect_type": [
      "status_immunity",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 10,
      "HP": 10,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Echo Crescendo of Shattered Melody",
    "effect_type": [
      "spd_buff",
      "atk_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Crystal Chord of Resounding Fate",
    "effect_type": [
      "spd_buff",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -2,
      "SPD": 15,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Echo Ember of Roaming Sparks",
    "effect_type": [
      "cloak",
      "bonus_damage"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Mistwhisper of Timeless Depth",
    "effect_type": [
      "def_buff",
      "ep_gain"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 0,
      "HP": 10,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Echo Torrent of Quiet Wisdom",
    "effect_type": [
      "buff_removal",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 0,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Prismdance of Silent Hymn",
    "effect_type": [
      "heal",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Illusion Echo of Shifting Veils",
    "effect_type": [
      "cloak",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Vulpine Waltz of Phantom Grace",
    "effect_type": [
      "bonus_damage",
      "burst"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 2,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Petal Echo of Secret Renewal",
    "effect_type": [
      "def_buff",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Lunar Echo of Starlit Arrow",
    "effect_type": [
      "aoe_damage",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 10,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Bowstring of Midnight Resolve",
    "effect_type": [
      "cloak",
      "taunt"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 2,
      "SPD": 10,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Flare Echo of Everlasting Rise",
    "effect_type": [
      "burn",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 6,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Blaze Echo of Forged Resolve",
    "effect_type": [
      "burst",
      "def_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 10,
      "SPD": 0,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Charcore of Unbroken Will",
    "effect_type": [
      "def_buff",
      "bonus_damage"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 10,
      "SPD": 0,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Petal Echo of Silent Shadows",
    "effect_type": [
      "cloak",
      "buff_removal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 2,
      "SPD": 10,
      "HP": 10,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Moonshard of Hidden Grace",
    "effect_type": [
      "heal",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Hammer Echo of Starforged Justice",
    "effect_type": [
      "def_ignore",
      "aoe_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": -2,
      "SPD": 8,
      "HP": 0,
      "EP": 8
    },
    "ep_cost": 95
  },
  {
    "title": "Vine Echo of Bound Growth",
    "effect_type": [
      "ep_gain",
      "def_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 0,
      "HP": 10,
      "EP": 10
    },
    "ep_cost": 85
  },
  {
    "title": "Thornsong of Rooted Protection",
    "effect_type": [
      "def_buff",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 0,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Torchlight of Hidden Truths",
    "effect_type": [
      "status_immunity",
      "buff_removal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Shadow Echo of Unseen Strike",
    "effect_type": [
      "cloak",
      "bonus_damage"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Dirge Echo of Midnight Sorrow",
    "effect_type": [
      "spd_buff",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Pillarbrand of Unfinished Dreams",
    "effect_type": [
      "revive",
      "def_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 6,
      "SPD": 0,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Crown Echo of Hidden Dominion",
    "effect_type": [
      "cloak",
      "burst"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 8
    },
    "ep_cost": 90
  },
  {
    "title": "Scepterburst of Covert Sovereignty",
    "effect_type": [
      "def_ignore",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 2,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Blade Echo of Bloodied Vow",
    "effect_type": [
      "burn",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 12,
      "DEF": 0,
      "SPD": 10,
      "HP": 5,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Arenaheart of Unyielding Grit",
    "effect_type": [
      "aoe_damage",
      "taunt"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 4,
      "SPD": 5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Smoldering Twist of Faith",
    "effect_type": [
      "burst",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 15,
      "DEF": 0,
      "SPD": 5,
      "HP": 10,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Threnody of the Stormbound Chamber",
    "effect_type": [
      "def_buff",
      "slow"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 15,
      "SPD": -5,
      "HP": 15,
      "EP": 10
    },
    "ep_cost": 95
  },
  {
    "title": "Wavebraid Gospel of the Moonspun Thread",
    "effect_type": [
      "heal",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -2,
      "SPD": 5,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Bloomscript Verse of the Vowkeeper's Wake",
    "effect_type": [
      "regen",
      "taunt"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 10,
      "SPD": 5,
      "HP": 15,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Veilthread Vision of the Seraph's Gate",
    "effect_type": [
      "cloak",
      "reflect"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 0,
      "HP": 15,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Lanternborn Litany of the Ember Choir",
    "effect_type": [
      "atk_buff",
      "silence"
    ],
    "target_type": "aoe_ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Silkblood Chant of the Autumn Veil",
    "effect_type": [
      "regen",
      "def_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 20,
      "SPD": 0,
      "HP": 20,
      "EP": 5
    },
    "ep_cost": 95
  },
  {
    "title": "Flickerbound Oath of the Forgotten Flame",
    "effect_type": [
      "burn",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": -5,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Palletborne Chronicle of the Grown Seed",
    "effect_type": [
      "regen",
      "slow"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 20,
      "SPD": -5,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Winewrought Liturgy of the Vigil Flame",
    "effect_type": [
      "cloak",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": -5,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 100
  },
  {
    "title": "Redcrest Vow of the Shrouded Vigilant",
    "effect_type": [
      "def_buff",
      "lifesteal"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 15,
      "SPD": 0,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 70
  },
  {
    "title": "Petalbound Oath of the Hollow Aurora",
    "effect_type": [
      "heal",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": 5,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 80
  },
  {
    "title": "Gospel of the Ultralight Garden",
    "effect_type": [
      "cloak",
      "def_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 15,
      "SPD": -5,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Scriptwoven Canticle of the Dual Thread",
    "effect_type": [
      "burst",
      "spd_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 10,
      "HP": -5,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Mirrorsong Verse of the Synthetic Bloom",
    "effect_type": [
      "lifesteal",
      "cloak"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 15,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Synthwoven Echo of the First Sound",
    "effect_type": [
      "heal",
      "atk_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 5,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Mythscript Verse of the Twilight Crest",
    "effect_type": [
      "status_immunity",
      "regen"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 5,
      "SPD": 0,
      "HP": 10,
      "EP": 5
    },
    "ep_cost": 85
  },
  {
    "title": "Lineagebound Echo of the Lunar Gate",
    "effect_type": [
      "atk_buff",
      "revive"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": 0,
      "SPD": 0,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Frostgilded Elegy of the Veiled Flame",
    "effect_type": [
      "slow",
      "burn"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 0,
      "SPD": -5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 75
  },
  {
    "title": "Ashenbound Vow of the Crimson Night",
    "effect_type": [
      "lifesteal",
      "bonus_damage"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": -5,
      "SPD": 7,
      "HP": -10,
      "EP": 5
    },
    "ep_cost": 90
  },
  {
    "title": "Tirobound Whisper of the Gracebound Sigil",
    "effect_type": [
      "shield",
      "status_immunity"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 15,
      "SPD": 0,
      "HP": 10,
      "EP": 0
    },
    "ep_cost": 85
  },
  {
    "title": "Tea-Laced Hymn of the Solitary Bloom",
    "effect_type": [
      "heal",
      "def_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 3,
      "DEF": 10,
      "SPD": 0,
      "HP": 20,
      "EP": 0
    },
    "ep_cost": 95
  },
  {
    "title": "Windscript Gospel of the Tireless Accord",
    "effect_type": [
      "spd_buff",
      "atk_buff"
    ],
    "target_type": "self",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 15,
      "HP": 0,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Canticle of the Dawnfold Vow",
    "effect_type": [
      "atk_buff",
      "heal"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 10,
      "DEF": 0,
      "SPD": 0,
      "HP": 15,
      "EP": 0
    },
    "ep_cost": 90
  },
  {
    "title": "Casparbound Liturgy of the Shattered Crest",
    "effect_type": [
      "stun",
      "def_ignore"
    ],
    "target_type": "enemy",
    "stat_modifiers": {
      "ATK": 5,
      "DEF": -5,
      "SPD": -5,
      "HP": 0,
      "EP": 10
    },
    "ep_cost": 90
  },
  {
    "title": "Gunpetal Verse of the Gilded Mourning",
    "effect_type": [
      "revive",
      "def_buff"
    ],
    "target_type": "ally",
    "stat_modifiers": {
      "ATK": 0,
      "DEF": 10,
      "SPD": 0,
      "HP": 15,
      "EP": 0
    },
    "ep_cost": 90
  }
]

def load_echo_titles(raw_data):
    echo_objects = []
    for echo_dict in raw_data:
        target_type = infer_target_type(echo_dict)
        echo = EchoTitle(
            title=echo_dict["title"],
            effect_type=echo_dict["effect_type"],
            stat_modifiers=echo_dict.get("stat_modifiers", {}),
            ep_cost=echo_dict["ep_cost"],
            target_type=target_type
        )
        echo_objects.append(echo)
    return echo_objects
# Load EchoTitles once
echo_objects = load_echo_titles(EchoTitles)

# Build lookup dictionaries
echo_lookup = {echo.title: echo for echo in echo_objects}
ECHO_LIB    = {echo.title: echo for echo in echo_objects}

# --- Selection Functions ---
def choose_team(available_pool=None):
    if available_pool is None:
        # Build full pool from houses
        available_pool = []
        for house, champs in houses.items():
            for c in champs:
                c["house"] = house
                available_pool.append(c)

    selected = []
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🧙 Choose Champions for Your Team")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Build house map
    house_map = {}
    for c in available_pool:
        house_map.setdefault(c["house"], []).append(c)

    house_list = list(house_map.keys())

    while len(selected) < 5:
        print(f"\n🏛️ Choose a House ({5 - len(selected)} picks left):")
        for i, h in enumerate(house_list, 1):
            print(f"  {i}. {h} ({len(house_map[h])} champions available)")
        print("  0. ✅ Finish team selection early")

        house_choice = input("Enter house number: ").strip()

        if house_choice == "0":
            print(f"🎯 Team selection finished with {len(selected)} champion(s).")
            break

        if not house_choice.isdigit() or not (1 <= int(house_choice) <= len(house_list)):
            print("❌ Invalid house selection.")
            continue

        chosen_house = house_list[int(house_choice) - 1]
        champions = house_map[chosen_house]

        while True:
            print(f"\n🎭 Champions in {chosen_house}:")
            for i, champ in enumerate(champions, 1):
                stats = champ.get("stats", {})
                echoes = champ.get("echo_titles", [])
                print(f"\n  {i}.  {champ['name']} — {champ.get('grand_title', 'No Title')}")
                print(f"     🩸 HP: {stats.get('HP', '?')}   ⚔️ ATK: {stats.get('ATK', '?')}   🛡️ DEF: {stats.get('DEF', '?')}   💨 SPD: {stats.get('SPD', '?')}")
                if echoes:
                    print(f"     🔮 Echoes: {', '.join(echoes)}")

            print("\n  0. 🔙 Go back to house selection")
            champ_choice = input("Enter champion number: ").strip()

            if champ_choice == "0":
                break

            if not champ_choice.isdigit() or not (1 <= int(champ_choice) <= len(champions)):
                print("❌ Invalid champion selection.")
                continue

            champ_data = champions[int(champ_choice) - 1]
            if champ_data["name"] in [c.name for c in selected]:
                print("⚠️ Champion already selected.")
                continue

            selected.append(Champion(champ_data))
            champions.remove(champ_data)
            print(f"✅ {champ_data['name']} added to your team!")
            break

    return selected


def show_team(team, team_name):
    print(f"\n👥 Team {team_name}:\n" + "=" * 50)
    for champ in team:
        champ.show_status()
        print("-" * 50)

# --- Duel Function ---
# Duel Function
def get_valid_targets(champ, team_enemies):
    taunt_targets = [e for e in team_enemies if e.status.has("taunt")]
    if taunt_targets:
        return taunt_targets
    return [e for e in team_enemies if not e.status.has("cloak")]

def validate_echo_targets(echo, user, target, allies, enemies):
    tt = echo.target_type
    if tt == "self":
        return target == user
    if tt == "ally":
        return target in allies and (target.is_alive() or "revive" in echo.effect_type)
    if tt == "enemy":
        return target in enemies and target.is_alive()
    if tt == "aoe_ally":
        return any(c.is_alive() or "revive" in echo.effect_type for c in allies)
    if tt == "aoe_enemy":
        return any(c.is_alive() for c in enemies)
    print(f"⚠️ Unknown target type '{tt}' for Echo '{echo.title}'")
    return False

def resolve_damage(attacker, target, base_damage, source=None):
    if not target.is_alive():
        return

    # 🛡️ Damage Negation
    if target.status.has("damage_negation"):
        target.status.remove("damage_negation")
        log(f"🛡️ {target.name} negates damage from '{source or 'basic attack'}'!")
        return

    # 🩰 Dodge (chance-based)
    dodge_effects = target.status.get("dodge")
    for e in dodge_effects:
        chance = e.get("value", 0.25)
        if random.random() < chance:
            log(f"🩰 {target.name} dodges the attack from {attacker.name}!")
            return

    # 🛡️ Shield absorption
    damage = max(base_damage, 1)
    shield_effects = target.status.get("shield")
    if shield_effects:
        shield = shield_effects[0]
        shield_hp = shield["value"]
        absorbed = min(damage, shield_hp)
        shield["value"] -= absorbed
        damage -= absorbed
        log(f"🛡️ {target.name}'s shield absorbs {absorbed} damage.")
        if shield["value"] <= 0:
            target.status.remove("shield")
            log(f"💥 {target.name}'s shield breaks!")

    # 💥 Apply damage
    target.hp = max(target.hp - damage, 0)
    log(f"⚔️ {attacker.name} deals {damage} damage to {target.name} via '{source or 'basic attack'}'.")

    # 🩸 Lifesteal
    lifesteal_effects = attacker.status.get("lifesteal")
    for e in lifesteal_effects:
        heal = int(damage * e.get("value", 0.3))
        attacker.hp = min(attacker.max_hp, attacker.hp + heal)
        log(f"🩸 {attacker.name} steals {heal} HP from {target.name}.")


def select_target(champ, valid_targets, player_team):
    if not valid_targets:
        return None
    if champ in player_team:
        print("Choose a target:")
        for i, t in enumerate(valid_targets, 1):
            status = "KO'd" if not t.is_alive() else f"{t.hp} HP"
            print(f"[{i}] {t.name} ({status})")
        try:
            choice = int(input("Target number: ")) - 1
            if 0 <= choice < len(valid_targets):
                return valid_targets[choice]
        except:
            print("❌ Invalid input. Target randomly selected.")
    return random.choice(valid_targets)

def choose_best_target(champ, echo, allies, enemies):
    if not echo:
        return random.choice([e for e in enemies if e.is_alive()])
    tt = echo.target_type
    if tt == "self":
        return champ
    elif tt == "ally":
        valid = [a for a in allies if a.is_alive()]
        if "revive" in echo.effect_type:
            valid = [a for a in allies if not a.is_alive()]
        return random.choice(valid) if valid else None
    elif tt == "enemy":
        valid = [e for e in enemies if e.is_alive()]
        return random.choice(valid) if valid else None
    elif tt in ["aoe_ally", "aoe_enemy"]:
        return None
    return None

def choose_best_echo(champ, allies, enemies):
    available = [e for e in champ.echoes if champ.ep >= e.ep_cost]
    return random.choice(available) if available else None

def duel(player_team, enemy_team, player_controlled=True, enemy_controlled=False):
    round_count = 1

    if DEBUG_MODE:
        for champ in player_team + enemy_team:
            champ.ep = 100

    while any(c.is_alive() for c in player_team) and any(c.is_alive() for c in enemy_team):
        print(f"\n🎯 Round {round_count}")
        all_fighters = sorted(player_team + enemy_team, key=lambda x: x.spd, reverse=True)

        for champ in all_fighters:
            if not champ.is_alive():
                continue

            champ.status.process(champ)

            team_allies = player_team if champ in player_team else enemy_team
            team_enemies = enemy_team if champ in player_team else player_team
            controlled = player_controlled if champ in player_team else enemy_controlled

            if not any(e.is_alive() for e in team_enemies):
                winner = "Dreamers" if champ in player_team else "Fixers"
                print(f"\n🏆 {champ.name} stands victorious — the opposing team has fallen!")
                print(f"\n🏆 {winner} win the Timeline Rupture!")
                print("\n📜 Battle History:")
                for entry in battle_history:
                    print(entry)
                return

            print(f"\n🔘 {champ.name}'s turn!")

            # Echo selection
            selected_echo = None
            available_echoes = [e for e in champ.echoes if champ.ep >= e.ep_cost]

            if available_echoes:
                if controlled:
                    print("\n💫 Cast an Echo?")
                    for idx, e in enumerate(champ.echoes, 1):
                        ep_ok = champ.ep >= e.ep_cost
                        status = "✅" if ep_ok else "❌"
                        print(f"[{idx}] {e.title} ({e.ep_cost} EP) {status} [Target: {e.target_type}]")

                    try:
                        echo_choice = int(input("Select Echo or 0 to skip: ")) - 1
                        if 0 <= echo_choice < len(champ.echoes):
                            selected_echo = champ.echoes[echo_choice]
                    except:
                        print("❌ Invalid input. Skipping Echo.")
                else:
                    selected_echo = choose_best_echo(champ, team_allies, team_enemies)

            # Target selection
            target = None
            if selected_echo:
                tt = selected_echo.target_type
                if tt == "self":
                    target = champ
                elif tt == "ally":
                    valid_targets = [c for c in team_allies if c.is_alive()]
                    if "revive" in selected_echo.effect_type:
                        valid_targets = [c for c in team_allies if not c.is_alive()]
                    target = select_target(champ, valid_targets, player_team) if controlled else choose_best_target(champ, selected_echo, team_allies, team_enemies)
                elif tt == "enemy":
                    valid_targets = get_valid_targets(champ, [e for e in team_enemies if e.is_alive()])
                    target = select_target(champ, valid_targets, player_team) if controlled else choose_best_target(champ, selected_echo, team_allies, team_enemies)
                elif tt in ["aoe_ally", "aoe_enemy"]:
                    target = None

                if champ.ep >= selected_echo.ep_cost and validate_echo_targets(selected_echo, champ, target, team_allies, team_enemies):
                    selected_echo.use(champ, target, team_allies, team_enemies)
                    continue
                else:
                    print("❌ Cannot cast that Echo right now.")

            # Fallback: basic attack
            fallback_targets = get_valid_targets(champ, [e for e in team_enemies if e.is_alive()])
            target = select_target(champ, fallback_targets, player_team) if controlled else choose_best_target(champ, None, team_allies, team_enemies)
            if target:
                resolve_damage(champ, target, champ.atk)

        # Show team status
        show_team(player_team, "Dreamers")
        show_team(enemy_team, "Fixers")

        # EP regeneration
        for champ in player_team + enemy_team:
            if champ.is_alive():
                champ.ep = min(champ.ep + champ.ep_per_turn, 100)

        round_count += 1

    winner = "Dreamers" if any(c.is_alive() for c in player_team) else "Fixers"
    print(f"\n🏆 {winner} win the Timeline Rupture!")
    print("\n📜 Battle History:")
    for entry in battle_history:
        print(entry)



# --- Main Game ---
def main():
    print("\n🎭 Welcome to 5v5 Dreamer Waltz — Timeline Rupture Mode")
    print("═══════════════════════════════════════════════════════")
    print("Choose your battle mode:")
    print("  1️⃣  Player vs AI      — You control Dreamers")
    print("  2️⃣  Player vs Player  — You control both teams")
    print("  3️⃣  AI vs AI          — Watch the simulation")
    print("═══════════════════════════════════════════════════════")

    # 🎭 Show mode selection
    mode = input("Enter mode number (1–3): ").strip()
    if mode not in {"1", "2", "3"}:
        print("❌ Invalid selection. Please choose 1, 2, or 3.")
        return

    print("\n🌟 Building your Dreamers team...")
    player_team = choose_team()

    # 🛠️ Build echo lookup
    echo_title_list = load_echo_titles(EchoTitles)
    echo_lookup = {echo.title: echo for echo in echo_title_list}

    # 🛠️ Build full champion pool with Echo objects
    all_champions = []
    for house, champs in houses.items():
        for c in champs:
            c["house"] = house
            echo_objs = [echo_lookup.get(title) for title in c.get("echo_titles", []) if echo_lookup.get(title)]
            c["echoes"] = echo_objs
            all_champions.append(c)

    # 🧠 Build enemy team
    used_names = [c.name for c in player_team]
    enemy_data = [c for c in all_champions if c["name"] not in used_names]

    if mode in {"1", "3"}:
        print("\n🧠 Do you want to manually select the Fixers team?")
        choice = input("Type 'yes' to choose manually, or press Enter to auto-generate: ").strip().lower()
        if choice == "yes":
            print("\n🌑 Building your Fixers team...")
            enemy_team = choose_team(available_pool=enemy_data)
        else:
            enemy_team = [Champion(c) for c in random.sample(enemy_data, 5)]
    else:
        enemy_team = [Champion(c) for c in random.sample(enemy_data, 5)]

    # 🎭 Show teams
    show_team(player_team, "Dreamers")
    show_team(enemy_team, "Fixers")

    input("\n💥 Press Enter to begin the duel...")

    # 🎮 Launch duel based on selected mode
    mode_map = {
        "1": (True, False),  # PvE
        "2": (True, True),   # PvP
        "3": (False, False)  # AI vs AI
    }
    player_controlled, enemy_controlled = mode_map[mode]

    print(f"\n🌀 Mode selected: {'Player vs AI' if mode == '1' else 'Player vs Player' if mode == '2' else 'AI vs AI'}")
    duel(player_team, enemy_team, player_controlled, enemy_controlled)


# 🚀 Run the game
if __name__ == "__main__":
    main()
