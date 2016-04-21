function groupBy( clusters , sortingFunction ) {

  var groupedClusters = Object.keys(clusters).map(function(cluster) {
    var children = (clusters[cluster].articles.length > 1) ? clusters[cluster].articles : [];
    return {
      'title': '',
      'children': children,
      'info': clusters[cluster],
      'cluster': cluster,
      'holder': true,
      'borderColor': "#A9C7FF"
    };
  }).sort(function(a, b) { return a.cluster - b.cluster });

  return groupedClusters
}

$.get('/text-mining/query', function(data) {
  data = JSON.parse(data);
  data.forEach(function(group, i) {
    $('#query > select[name="group"]').append('<option value="'+group+'"]>'+group+'</option>')
  });
});

$('#query').submit(function(e) {
  e.preventDefault();

  var group = $(this).find('[name="group"]').val();

  $('#canvas, #hiddenCanvas').remove();

  $('.spinner-holder').show();

  $.post('/text-mining/query', JSON.stringify({'group': group}), function (data) {
    data = JSON.parse(data);
    if (data.error === 'bad query') {
      alert('It appears we couldn\'t generate useful clusters with your query, please try another.');
      $('.spinner-holder').hide();
      return;
    }
    
    var dataset = {
      'title': '',
      'children': groupBy(data, function(obj) {return obj['cluster']}),
      'top': true
    };

    $('.spinner-holder').hide();

    drawAll(function(err){ console.log(err) }, dataset);
  });

  return false;
});

$('#query').submit()

  
function drawAll(error, dataset) {
  ////////////////////////////////////////////////////////////// 
  ////////////////// Create Set-up variables  ////////////////// 
  ////////////////////////////////////////////////////////////// 

  var width = Math.max($("#chart").width(),350) - 10,
    height = (window.innerWidth < 768 ? width : window.innerHeight - 10);

  var mobileSize = (window.innerWidth < 768 ? true : false);

  var centerX = width/2,
    centerY = height/2;

  ////////////////////////////////////////////////////////////// 
  /////////////////////// Create SVG  /////////////////////// 
  ////////////////////////////////////////////////////////////// 
  
  //Create the visible canvas and context
  var canvas  = d3.select("#chart").append("canvas")
    .attr("id", "canvas")
    .attr("width", width)
    .attr("height", height);
  var context = canvas.node().getContext("2d");
    context.clearRect(0, 0, width, height);
  
  //Create a hidden canvas in which each circle will have a different color
  //We can use this to capture the clicked on circle
  var hiddenCanvas  = d3.select("#chart").append("canvas")
    .attr("id", "hiddenCanvas")
    .attr("width", width)
    .attr("height", height)
    .style("display","none"); 
  var hiddenContext = hiddenCanvas.node().getContext("2d");
    hiddenContext.clearRect(0, 0, width, height);

  //Create a custom element, that will not be attached to the DOM, to which we can bind the data
  var detachedContainer = document.createElement("custom");
  var dataContainer = d3.select(detachedContainer);

  ////////////////////////////////////////////////////////////// 
  /////////////////////// Create Scales  /////////////////////// 
  ////////////////////////////////////////////////////////////// 

  var colorCircle = d3.scale.ordinal()
      .domain([0,1,2,3])
      .range(['#555','#4c73dd','#4c4c4c','#1c1c1c']);

  var diameter = Math.min(width*0.9, height*0.9),
    radius = diameter / 2;
    
  var zoomInfo = {
    centerX: width / 2,
    centerY: height / 2,
    scale: 1
  };

  //Dataset to swtich between color of a circle (in the hidden canvas) and the node data  
  var colToCircle = {};
  
  var pack = d3.layout.pack()
    .padding(1)
    .size([diameter, diameter])
    .value(function(d) { return d.distance * 100; })
    .sort(function(d) { return d.ID; });

  var bubbleColor = d3.scale.linear()
    .range(['#253C78', '#C576FF']);
    // .range(['#FF7A91', '#B3FFB4']);

  ////////////////////////////////////////////////////////////// 
  ////////////////// Create Circle Packing /////////////////////
  ////////////////////////////////////////////////////////////// 

  var nodes = pack.nodes(dataset),
    oldNode = {},
    currentNode = {},
    holders = [],
    activeCluster = -1,
    root = dataset,
    focus = root;
  
  for (var i=0; i<nodes.length; i++) {
    if (nodes[i].holder) {
      holders.push(nodes[i]);
    }
  }
  ////////////////////////////////////////////////////////////// 
  ///////////////// Canvas draw function ///////////////////////
  ////////////////////////////////////////////////////////////// 
  
  var cWidth = canvas.attr("width");
  var cHeight = canvas.attr("height");
  var nodeCount = nodes.length;
  var drawText = true;
  var mouseX = 0,
    mouseY = 0;

  function updateSize() {
    width = Math.max($("#chart").width(),350) - 10,
    height = (window.innerWidth < 768 ? width : window.innerHeight - 10);
    centerX = width/2;
    centerY = height/2;
    zoomInfo = {
      centerX: width / 2,
      centerY: height / 2,
      scale: 1
    };
  }

  function keywordsOverlayRect(context, node) {
    context.save();

    context.beginPath();
    context.arc(
      ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX,
      ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY,
      node.r * zoomInfo.scale, 0,  2 * Math.PI, true
    );
    context.clip();

    context.fillStyle = "rgba(255,255,255,0.75)";
    context.fillRect(
      ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX - (node.r*zoomInfo.scale),
      ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY - 25,
      (node.r*2)*zoomInfo.scale,
      50
    );

    context.restore();
  }

  function wrapText(context, node) {
    var lineHeight = 16;
    if (node.children && !(node.children.length > 1)) return;

    context.font = '14px proxima-nova-400';
    var maxWidth = (Math.sin(Math.PI/4) * node.r * zoomInfo.scale)*2 - 6;
    var y = ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY;

    if (node.holder) {
      context.textAlign = "center";
      keywordsOverlayRect(context, node);
      context.fillStyle = '#333';
      var words = node.info.title_keywords.join(', ').split(' ');
      var x = ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX;
      var maxHeight = 50;
    } else {
      context.textAlign = "left";
      context.fillStyle = '#fff';
      var words = node.title.split(' ');
      var x = ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX - (maxWidth/2) + 3;
      var maxHeight = maxWidth;
    }
    
    var currentLine = '';
    var lines = []

    for(var n = 0; n < words.length; n++) {

      var testLine = currentLine + words[n] + ' ';
      var metrics = context.measureText(testLine);
      var testWidth = metrics.width;

      if (testWidth > maxWidth && n > 0) {
        lines.push(currentLine);
        currentLine = words[n] + ' ';
      } else {
        currentLine = testLine
      }
    }
    lines.push(currentLine)
    lines = lines.slice(0, Math.floor(maxHeight/lineHeight));
    
    for (var i=0; i<lines.length; i++) {
      context.fillText(lines[i], x, y - (lines.length*lineHeight)/2 + (i*lineHeight) + 8);
    }
  }

  // The draw function of the canvas that gets called on each frame
  function drawCanvas(chosenContext, hidden) {

    //Clear canvas
    chosenContext.fillStyle = "#555";
    chosenContext.rect(0,0,cWidth,cHeight);
    chosenContext.fill();
    
    //Select our dummy nodes and draw the data to canvas.
    var node = null;
    // It's slightly faster than nodes.forEach()
    for (var i = 0; i < nodeCount; i++) {
      node = nodes[i];

      //If the hidden canvas was send into this function and it does not yet have a color, generate a unique one
      if (hidden) {
        if(node.color == null) {
          // If we have never drawn the node to the hidden canvas get a new color for it and put it in the dictionary.
          node.color = genColor();
          colToCircle[node.color] = node;
        }// if
        // On the hidden canvas each rectangle gets a unique color.
        chosenContext.fillStyle = node.color;
      } else {
        chosenContext.fillStyle = (node.children || node.indico == undefined) ? colorCircle(node.depth) : bubbleColor(node.indico.sentimenthq);
      }// else

      chosenContext.lineWidth = 3;
      if (node.border != true || node.top == true) {
        chosenContext.strokeStyle = "rgba(255,255,255,0)";
      } else if (node.holder && node.border != true) {
        chosenContext.strokeStyle = "rgba(255,255,255,0.75)";
      } else {
        chosenContext.strokeStyle = node.borderColor;
      }
    
      // Draw each circle
      chosenContext.beginPath();
      chosenContext.arc(
        ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX,
        ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY,
        node.r * zoomInfo.scale, 0,  2 * Math.PI, true
      );
      chosenContext.fill();
      chosenContext.stroke();

      if (node.cluster == focus.cluster && !node.holder && drawText) {
        wrapText(context, node);
      }

      //There are several options for setting text
      // chosenContext.font = "20px Open Sans";
      //textAlign supports: start, end, left, right, center
      chosenContext.textAlign = "center";
      //textBaseline supports: top, hanging, middle, alphabetic, ideographic bottom
      chosenContext.textBaseline = "middle";
      chosenContext.fillStyle = "#4169E1";    
    }//for i

    for (var i=0; i<holders.length; i++) {
      var holder = holders[i];

      if (!(holder.cluster == activeCluster) && holder.children) {
        if (focus.cluster != holder.cluster) wrapText(context, holder);
      }
    } // for i in holders

  }//function drawCanvas

  ////////////////////////////////////////////////////////////// 
  /////////////////// Click functionality ////////////////////// 
  ////////////////////////////////////////////////////////////// 

  function findCluster(node) {
    return holders.find(function(holder) {
      return holder.cluster == node.cluster;
    });
  }

  function slideInfoOut(node) {
    updateText(node, ['keywords', 'people', 'places', 'organizations'], '#info');
    $('#info .text').html(node.text);

    $('#info .title').find('a').attr('href', node.link);
    $('#info .title').find('a').text(node.title);

    $('#info').css({'right': '0px'});
    $('#chart').css({'right': '200px'});
    updateSize();
  }

  function slideInfoIn() {
    $('#info').css({'right': '-400px'});
    $('#chart').css({'right': '0px'});
    updateSize();
  }
  
  // Listen for clicks on the main canvas
  document.getElementById("canvas").addEventListener("click", function(e){
    //Figure out where the mouse click occurred.
    mouseX = e.layerX;
    mouseY = e.layerY;
    // Get the corresponding pixel color on the hidden canvas and look up the node in our map.
    // This will return that pixel's color
    var col = hiddenContext.getImageData(mouseX, mouseY, 1, 1).data;
    //Our map uses these rgb strings as keys to nodes.
    var colString = "rgb(" + col[0] + "," + col[1] + ","+ col[2] + ")";
    currentNode = colToCircle[colString];

    // We actually only need to draw the hidden canvas when there is an interaction. 
    // This sketch can draw it on each loop, but that is only for demonstration.
    drawCanvas(hiddenContext, true);
    for (var i=0; i<nodeCount; i++) {
      var node = nodes[i];
      
      if (node.selected) {
        node.border = false;
        node.borderColor = '#b05ecc';
        node.selected = false;
      }
    }

    if (currentNode) {
      var cluster = findCluster(currentNode);
      if (cluster && currentNode.top !== true) {
        zoomToCanvas(cluster);
        if (currentNode.holder !== true) slideInfoOut(currentNode);
      } else {
        zoomToCanvas(root);
        slideInfoIn();
      }

      currentNode.selected = true;
    }//if

  });

  ////////////////////////////////////////////////////////////// 
  /////////////////// Hover functionality ////////////////////// 
  //////////////////////////////////////////////////////////////
  function uniqueBy(a, key) {
      var seen = {};
      return a.filter(function(item) {
          var k = key(item);
          return seen.hasOwnProperty(k) ? false : (seen[k] = true);
      });
  }

  function showTop (article, indicoSelector) {
    var uniques = uniqueBy(article.indico[indicoSelector], function(obj) { return obj.text });
    return uniques.slice(0, 3).map(function(entityMetadata) {
      return entityMetadata.text;
    }).join(', ');
  }

  function updateText(node, listOfSelectors, parent) {
    var parent = parent || '';
    for (var i=0; i<listOfSelectors.length; i++) {
      var selector = listOfSelectors[i];

      if (node.indico[selector].length > 0) {
        var info = showTop(node, selector);

        $(parent+' .'+selector).html('\
          <p><b>'+selector[0].toUpperCase()+selector.slice(1)+'</b><br>\
          '+info+'</p>')
      } else {
        $(parent+' .'+selector).html('')
      }
    }
  }

  function setTooltip (node, mouseX, mouseY) {
    if (node.holder == true || node.top == true) {
      $('#tooltip').stop(true, true);
      $('#tooltip').hide();
      return;
    }

    // updateText(node, ['keywords', 'people', 'places', 'organizations'], '#tooltip');
    var top = (centerY > mouseY) ? mouseY-80 : mouseY-$('#tooltip').height();
    var left = (centerX > mouseX) ? mouseX+75 : mouseX-375;
    // var nodeX = ((node.x - zoomInfo.centerX) * zoomInfo.scale) + centerX;
    // var nodeY = ((node.y - zoomInfo.centerY) * zoomInfo.scale) + centerY;
    // var top = (centerY > nodeX) ? nodeY-20 : nodeY-$('#tooltip').height();
    // var left = nodeX+50;

    $('#tooltip').css("top", top.toString()+"px");
    $('#tooltip').css("left", left.toString()+"px");
    $('#tooltip .title').text(node.title);
    
    $('#tooltip').stop(true, true);
    $('#tooltip').show();
  }

  function setBanner(node) {
    if (node.top == true || node.cluster == undefined) {
      $('#banner').stop(true, true);
      $('#banner').fadeOut();
      return
    } else {
      $('#banner').stop(true, true);
      $('#banner').fadeIn();
    }

    var clusterIndico = findCluster(node).info;
    var info = clusterIndico.people.join(', ')+', '+clusterIndico.places.join(', ');
    
    $('#banner > span').text(info);
  }

  document.getElementById('tooltip').addEventListener('mouseover', function(e) {
    $('#tooltip').stop(true, true);
    $('#tooltip').hide();
  });

  document.getElementById("canvas").addEventListener("mousemove", function(e) {
    //Figure out where the mouse click occurred.
    mouseX = e.layerX;
    mouseY = e.layerY;

    // Get the corresponding pixel color on the hidden canvas and look up the node in our map.
    // This will return that pixel's color
    var col = hiddenContext.getImageData(mouseX, mouseY, 1, 1).data;
    //Our map uses these rgb strings as keys to nodes.
    var colString = "rgb(" + col[0] + "," + col[1] + ","+ col[2] + ")";
    currentNode = colToCircle[colString];

    if (!Object.is(oldNode, currentNode)) {
      oldNode = currentNode;
      
      // We actually only need to draw the hidden canvas when there is an interaction. 
      // This sketch can draw it on each loop, but that is only for demonstration. 
      drawCanvas(hiddenContext, true);

      for (var i=0; i<nodeCount; i++) {
        var node = nodes[i]
        node.border = false;
        node.borderColor = (node.top == true)? 'rgba(255,255,255,0)' : 'rgba(255,255,255,0.75)';
        if (node.selected || node.holder) {
          node.border = true;
          node.borderColor = (node.selected) ? '#b05ecc' : 'rgba(255,255,255,0.75)';
        }
      }

      if (currentNode) {
        currentNode.border = true;
        activeCluster = (currentNode.top)? -1 : currentNode.cluster;

        if (currentNode.cluster != undefined) {
          var cluster = findCluster(currentNode);
          cluster.border = true;
        }
        setBanner(currentNode);
        setTooltip(currentNode, e.clientX, e.clientY);
      }
    }

  });

  ////////////////////////////////////////////////////////////// 
  ///////////////////// Zoom Function //////////////////////////
  ////////////////////////////////////////////////////////////// 
  
  //Based on the generous help by Stephan Smola
  //http://bl.ocks.org/smoli/d7e4f9199c15d71258b5
  
  var ease = d3.ease("cubic-in-out"),
    duration = 2000,
    timeElapsed = 0,
    interpolator = null,
    vOld = [focus.x, focus.y, focus.r * 2.05];
    
  //Create the interpolation function between current view and the clicked on node
  function zoomToCanvas(focusNode) {
    focus = focusNode;
    
    $('#tooltip').hide();
    drawText = false;

    var v = [focusNode.x, focusNode.y, focusNode.r * 2.05]; //The center and width of the new "viewport"
    
    interpolator = d3.interpolateZoom(vOld, v); //Create interpolation between current and new "viewport"
    
    duration =  interpolator.duration; //Interpolation gives back a suggested duration      
    timeElapsed = 0; //Set the time elapsed for the interpolateZoom function to 0 
    vOld = v; //Save the "viewport" of the next state as the next "old" state
  }//function zoomToCanvas
  
  //Perform the interpolation and continuously change the zoomInfo while the "transition" occurs
  function interpolateZoom(dt) {
    if (interpolator) {
      timeElapsed += dt;
      var t = ease(timeElapsed / duration);
      
      zoomInfo.centerX = interpolator(t)[0];
      zoomInfo.centerY = interpolator(t)[1];
      zoomInfo.scale = diameter / interpolator(t)[2];
    
      if (timeElapsed >= duration) {
        interpolator = null;
        drawText = true;
      }
    }//if
  }//function interpolateZoom
  
  ////////////////////////////////////////////////////////////// 
  //////////////////// Other Functions /////////////////////////
  ////////////////////////////////////////////////////////////// 
  
  //Generates the next color in the sequence, going from 0,0,0 to 255,255,255.
  //From: https://bocoup.com/weblog/2d-picking-in-canvas
  var nextCol = 1;
  function genColor(){
    var ret = [];
    // via http://stackoverflow.com/a/15804183
    if(nextCol < 16777215){
      ret.push(nextCol & 0xff); // R
      ret.push((nextCol & 0xff00) >> 8); // G 
      ret.push((nextCol & 0xff0000) >> 16); // B

      nextCol += 100; // This is exagerated for this example and would ordinarily be 1.
    }
    var col = "rgb(" + ret.join(',') + ")";
    return col;
  }//function genColor

  ////////////////////////////////////////////////////////////// 
  /////////////////////// Initiate ///////////////////////////// 
  ////////////////////////////////////////////////////////////// 
      
  //First zoom to get the circles to the right location
  zoomToCanvas(root);
  
  var dt = 0;
  d3.timer(function(elapsed) {
    interpolateZoom(elapsed - dt);
    dt = elapsed;
    drawCanvas(context);
  });

}//drawAll