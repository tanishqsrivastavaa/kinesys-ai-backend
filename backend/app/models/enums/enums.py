from enum import Enum, StrEnum


class ProcessingStatus(str, Enum):
    PENDING = "pending"       # Uploaded to S3, waiting for Agent
    PROCESSING = "processing" # Agent is currently "looking" at it
    COMPLETED = "completed"   # Data extracted successfully
    FAILED = "failed"


class LeadSource(StrEnum):
    WEBSITE = "Website"
    LINKEDIN = "LinkedIn"
    REFERRAL = "Referral"
    TRADE_SHOW = "TradeShow"
    COLD_CALL = "ColdCall"
    ADVERTISEMENT = "Advertisement"
    PARTNER = "Partner"
    OTHER = "Other"


class LeadStage(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"

    @property
    def label(self) -> str:
        return self.value.capitalize()

    @property
    def color(self) -> str:
        colors = {
            "new": "#6B7280",
            "contacted": "#3B82F6",
            "qualified": "#10B981",
            "proposal": "#F59E0B",
            "negotiation": "#8B5CF6",
            "won": "#059669",
            "lost": "#EF4444",
        }
        return colors.get(self.value, "#6B7280")


class LeadTemperature(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"

    @property
    def label(self) -> str:
        return self.value.capitalize()

    @property
    def color(self) -> str:
        colors = {
            "hot": "#EF4444",
            "warm": "#F97316",
            "cold": "#3B82F6",
        }
        return colors.get(self.value, "#6B7280")


class LeadIndustry(StrEnum):
    TECHNOLOGY = "Technology"
    HEALTHCARE = "Healthcare"
    FINANCE = "Finance"
    RETAIL = "Retail"
    MANUFACTURING = "Manufacturing"
    EDUCATION = "Education"
    REAL_ESTATE = "Real Estate"
    CONSULTING = "Consulting"
    MEDIA = "Media"
    OTHER = "Other"


class LeadTerritory(StrEnum):
    NORTH_AMERICA = "North America"
    EUROPE = "Europe"
    ASIA_PACIFIC = "Asia Pacific"
    LATIN_AMERICA = "Latin America"
    MIDDLE_EAST = "Middle East"
    AFRICA = "Africa"


class EmployeeCount(StrEnum):
    SOLO = "1-10"
    SMALL = "11-50"
    MEDIUM = "51-200"
    LARGE = "201-500"
    ENTERPRISE = "501-1000"
    MEGA = "1000+"