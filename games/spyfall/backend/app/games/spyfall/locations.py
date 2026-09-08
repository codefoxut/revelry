from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    key: str
    display_name: str
    roles: tuple[str, ...]


_LOCATIONS: tuple[Location, ...] = (
    Location("airplane", "Airplane", ("Pilot", "Co-Pilot", "Flight Attendant", "Mechanic", "Air Marshal", "First Class Passenger", "Economy Passenger")),
    Location("bank", "Bank", ("Manager", "Security Guard", "Teller", "Armored Car Driver", "Consultant", "Customer", "IT Technician")),
    Location("beach", "Beach", ("Lifeguard", "Ice Cream Vendor", "Photographer", "Surfer", "Beachcomber", "Tourist", "Volleyball Player")),
    Location("casino", "Casino", ("Dealer", "Bartender", "Security Guard", "High Roller", "Bouncer", "Waitress", "Manager")),
    Location("cathedral", "Cathedral", ("Priest", "Choir Singer", "Tourist", "Organist", "Bell Ringer", "Groundskeeper", "Bride")),
    Location("circus_tent", "Circus Tent", ("Ringmaster", "Acrobat", "Clown", "Animal Trainer", "Juggler", "Ticket Collector", "Magician")),
    Location("corporate_party", "Corporate Party", ("CEO", "Secretary", "Accountant", "HR Director", "Intern", "Salesperson", "IT Technician")),
    Location("crusader_army", "Crusader Army", ("Knight", "Monk", "Bishop", "Squire", "Archer", "Prisoner", "Servant")),
    Location("day_spa", "Day Spa", ("Massage Therapist", "Manicurist", "Stylist", "Client", "Plastic Surgeon", "Dermatologist", "Beautician")),
    Location("embassy", "Embassy", ("Ambassador", "Security Guard", "Secretary", "Tourist", "Refugee", "Diplomat", "Government Official")),
    Location("hospital", "Hospital", ("Surgeon", "Nurse", "Anesthesiologist", "Patient", "Intern", "Therapist", "Visitor")),
    Location("hotel", "Hotel", ("Bellhop", "Concierge", "Doorman", "Housekeeper", "Manager", "Customer", "Security Guard")),
    Location("military_base", "Military Base", ("General", "Sergeant", "Private", "Medic", "Officer", "Tank Engineer", "Cook")),
    Location("movie_studio", "Movie Studio", ("Director", "Actor", "Cameraman", "Producer", "Stuntman", "Sound Engineer", "Costume Designer")),
    Location("ocean_liner", "Ocean Liner", ("Captain", "Bartender", "Waiter", "Musician", "Mechanic", "Rich Passenger", "Cook")),
    Location("passenger_train", "Passenger Train", ("Conductor", "Engineer", "Waiter", "Passenger", "Stoker", "Restaurant Chef", "Border Patrol")),
    Location("pirate_ship", "Pirate Ship", ("Captain", "Cabin Boy", "Cook", "Navigator", "Bound Prisoner", "First Mate", "Swabbie")),
    Location("polar_station", "Polar Station", ("Scientist", "Cook", "Doctor", "Geologist", "Radioman", "Hydrologist", "Expedition Leader")),
    Location("police_station", "Police Station", ("Detective", "Lawyer", "Journalist", "Criminal", "Interrogator", "Archivist", "Chief")),
    Location("restaurant", "Restaurant", ("Chef", "Waiter", "Customer", "Food Critic", "Musician", "Manager", "Dishwasher")),
    Location("school", "School", ("Teacher", "Student", "Principal", "Security Guard", "Janitor", "Coach", "Cafeteria Worker")),
    Location("service_station", "Service Station", ("Manager", "Mechanic", "Cashier", "Customer", "Tire Specialist", "Electrician", "Delivery Driver")),
    Location("space_station", "Space Station", ("Commander", "Scientist", "Doctor", "Engineer", "Pilot", "Astrobiologist", "Technician")),
    Location("submarine", "Submarine", ("Captain", "Cook", "Sonar Technician", "Navigator", "Electronics Engineer", "Sailor", "Radioman")),
    Location("supermarket", "Supermarket", ("Cashier", "Butcher", "Security Guard", "Customer", "Store Clerk", "Cleaner", "Manager")),
    Location("theater", "Theater", ("Director", "Actor", "Coat Check Attendant", "Prompter", "Ticket Collector", "Cashier", "Musician")),
    Location("university", "University", ("Professor", "Student", "Dean", "Graduate Student", "Janitor", "Security Guard", "Coach")),
    Location("amusement_park", "Amusement Park", ("Ride Operator", "Tourist", "Security Guard", "Mascot", "Ticket Booth Worker", "Food Vendor", "Photographer")),
)

LOCATION_REGISTRY: dict[str, Location] = {location.key: location for location in _LOCATIONS}
