//	Hides flashed messages
function closeFlashed() {
	document.getElementById('alert').style.display = 'none';
}

/*
*	nav.html scripts: 
*/

//	Get and format list for autocomplete function
var search_terms = document.getElementById("autosuggestions").textContent;
search_terms = search_terms.split('\n');
for (i=0; i<search_terms.length; i++) {
	try {
		search_terms[i] = search_terms[i].split(",");
		search_terms[i][1] = ' ' + search_terms[i][1];
	} catch(err){};
};

// match function for "findResults" function
function autocompleteMatch(input) {
	if (input == '') {
		return [];
	};
	input = input.toUpperCase();
	var reg = new RegExp(input)
	return search_terms.filter(function(term) {
		if (term[0].match(reg)) {
		return term;
		};
	});
};
 
//	Takes input from navbar search input form
//	and renders matches input autosuggestion list
//	under the search input form
function findResults(val) {
	res = document.getElementById("results");
	res.innerHTML = '';
	let list = '';
	let terms = autocompleteMatch(val);
	for (i=0; i<terms.length; i++) {
		list += '<a href=/query/' + terms[i] + '><li>' + terms[i] + '</li></a>';
		if (i < terms.length - 1) {
			list += '<div class="divider"></div>';
		};
	};
	if (list.length != 0) {
		res.innerHTML = '<ul>' + list + '</ul>';
	};
};

//	Shows autosuggestion list 
function showResults() {
	document.getElementById("results").className = 'show';
}

//	Hides autosuggestion list
function hideResults() {
	setTimeout(function() {
		document.getElementById("results").className = 'hide';
	}, 100)
}

//	Focuses the 'username' input form when dropdown menu is opened.
//	(requires a short pause to ensure menu is open before attempting to direct focus)
function focusUsername() {
	setTimeout(function() {
		if (document.getElementById('loginDropdown').getAttribute('aria-expanded') == 'true') {
				document.getElementById("username").focus();
		};
	}, 100);
}
