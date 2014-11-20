#!/usr/bin/perl
use DateTime;
use DateTime::Format::ISO8601;
use DateTime::Format::MySQL;
while(<>)
{
        (my $datetime,$v) = split(/,/);
#print "read: $datetime\n";
        $datetime =~ s/\s/T/;
#print "modified 1: $datetime\n";
        $datetime .= "Z";
#print "modified 2: $datetime\n";
        chomp($v);
        my $dt_class = 'DateTime::Format::ISO8601';
        my $dt = $dt_class->parse_datetime($datetime);
        $dt->set_time_zone( 'Australia/Melbourne' );
        $dtfmysql = DateTime::Format::MySQL->format_datetime($dt);
        printf "%s,%s,8\n",$dtfmysql,$v;
}
