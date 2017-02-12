select cards.cardname,
cards.playerclass,
case 
	when deck_lists.cardname is null then 0 
	else count(*)
end as [Total],
case 
when deck_lists.cardname is null then 0.0
else count(*)/355.0 * 100.0
end as [Percent],
avg(coalesce(deck_lists.amount, 0)) as [Average Per Deck]
from cards
left join deck_lists
on cards.cardname = deck_lists.cardname
where cards.cardset in ('Classic', 'Whispers of the Old Gods', 'Mean Streets of Gadgetzan', 'The Grand Tournament')
and cards.playerclass <> 'Neutral'
group by cards.cardname
order by Percent desc
