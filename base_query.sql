select cards.cardname,
	   cards.hero,
	   case
	       when deck_lists.cardname is null then 0
	       else count(*)
	   end as [total],
	   case
	       when deck_lists.cardname is null then 0.0
		   else count(*)/(select cast(count(*) as double) from decks) * 100.0
	   end as [percent],
	   avg(coalesce(deck_lists.amount, 0)) as [per deck],
	   coalesce(collection.amount, 0) as collected
from cards
left join deck_lists
on cards.cardname = deck_lists.cardname
left join collection
on cards.cardname = collection.cardname
where cards.cardset in ('Classic',
						'Whispers of the Old Gods',
                        'Mean Streets of Gadgetzan',
						'Journey to Un''Goro')
group by cards.cardname
order by Total desc